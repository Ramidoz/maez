#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

TAG="b9596"
COMMIT="18ef86ecec723361362a332a79b4d913fd724d40"
VERSION="9596"
OFFICIAL_ORIGIN_HTTPS="https://github.com/ggml-org/llama.cpp.git"
OFFICIAL_ORIGIN_SSH="git@github.com:ggml-org/llama.cpp.git"
SOURCE_ROOT="/home/rohit/llama.cpp-release/source"
EXPECTED_OUTPUT_DIR="/home/rohit/llama.cpp-release/llama-b9596-cuda13.2-sm89"
INCUMBENT_DIR="/home/rohit/llama.cpp-release/llama-b9596/llama-b9596"
CUDA_ROOT="/usr/local/cuda-13.2"
NVCC="/usr/local/cuda-13.2/bin/nvcc"
CUDA_LIBRARY_ROOT="/usr/local/cuda-13.2/targets/x86_64-linux/lib"
FLOATING_CUDA_ROOT="/usr/local/cuda"
MANIFEST_NAME="runtime-manifest.sha256"

SOURCE_DIR=""
OUTPUT_DIR=""
BUILD_DIR=""
STAGE_DIR=""

usage() {
    printf 'usage: %s --source-dir ABSOLUTE_PATH --output-dir ABSOLUTE_PATH\n' "$0" >&2
}

die() {
    printf 'build_llama_b9596_cuda: %s\n' "$1" >&2
    exit 1
}

canonical_existing_dir() {
    local path="$1"
    local resolved
    [[ "$path" == /* ]] || die "path_not_absolute"
    [[ -d "$path" && ! -L "$path" ]] || die "directory_unavailable"
    resolved=$(realpath -e -- "$path")
    [[ "$resolved" == "$path" ]] || die "path_not_canonical"
    printf '%s\n' "$resolved"
}

canonical_future_path() {
    local path="$1"
    local resolved
    local parent
    local parent_resolved
    [[ "$path" == /* && "$path" != "/" ]] || die "path_not_absolute"
    resolved=$(realpath -m -- "$path")
    [[ "$resolved" == "$path" ]] || die "path_not_canonical"
    parent=$(dirname -- "$path")
    [[ -d "$parent" && ! -L "$parent" ]] || die "output_parent_unavailable"
    parent_resolved=$(realpath -e -- "$parent")
    [[ "$parent_resolved" == "$parent" ]] || die "output_parent_not_canonical"
    printf '%s\n' "$resolved"
}

refuse_existing_path() {
    local path="$1"
    [[ ! -e "$path" && ! -L "$path" ]] || die "destination_exists"
}

path_is_within() {
    local candidate="$1"
    local root="$2"
    [[ "$candidate" == "$root" || "$candidate" == "$root/"* ]]
}

require_pairwise_disjoint() {
    local -a paths=("$@")
    local left
    local right
    for ((left = 0; left < ${#paths[@]}; left++)); do
        for ((right = left + 1; right < ${#paths[@]}; right++)); do
            if path_is_within "${paths[$left]}" "${paths[$right]}" || \
                path_is_within "${paths[$right]}" "${paths[$left]}"; then
                die "path_collision"
            fi
        done
    done
}

require_source_generated_residue_absent() {
    local source="$1"
    local relative
    for relative in tools/ui/node_modules tools/ui/.svelte-kit tools/ui/dist; do
        [[ ! -e "$source/$relative" && ! -L "$source/$relative" ]] || \
            die "source_generated_residue"
    done
}

read_symlink_target() {
    local link_path="$1"
    local captured
    captured=$(
        readlink -n -- "$link_path" || exit 1
        printf '\034'
    ) || die "staged_symlink_invalid"
    SYMLINK_TARGET=${captured%$'\034'}
}

contains_manifest_control() {
    local value="$1"
    [[ "$value" == *$'\n'* ]] && return 0
    printf '%s' "$value" | LC_ALL=C grep -q $'[\001-\037\177-\237]'
}

validate_staged_symlinks() {
    local stage="$1"
    local symlink
    local current
    local resolved
    local hops
    stage=$(realpath -e -- "$stage") || die "staged_symlink_invalid"
    [[ -d "$stage" && ! -L "$stage" ]] || die "staged_symlink_invalid"

    while IFS= read -r -d '' symlink; do
        current="$symlink"
        hops=0
        while [[ -L "$current" ]]; do
            read_symlink_target "$current"
            [[ -n "$SYMLINK_TARGET" && "$SYMLINK_TARGET" != /* ]] || \
                die "staged_symlink_invalid"
            [[ "$SYMLINK_TARGET" != "." && "$SYMLINK_TARGET" != ".." ]] || \
                die "staged_symlink_invalid"
            [[ "$SYMLINK_TARGET" != */* ]] || die "staged_symlink_invalid"
            current="$stage/$SYMLINK_TARGET"
            ((hops += 1))
            ((hops <= 128)) || die "staged_symlink_invalid"
        done
        [[ -f "$current" ]] || die "staged_symlink_invalid"
        resolved=$(realpath -e -- "$current") || die "staged_symlink_invalid"
        path_is_within "$resolved" "$stage" || die "staged_symlink_invalid"
        [[ "$resolved" == "$current" ]] || die "staged_symlink_invalid"
    done < <(find "$stage" -mindepth 1 -maxdepth 1 -type l -print0 | LC_ALL=C sort -z)
}

validate_manifest_inputs() {
    local stage="$1"
    local entry
    local relative
    stage=$(realpath -e -- "$stage") || die "manifest_input_invalid"
    [[ -d "$stage" && ! -L "$stage" ]] || die "manifest_input_invalid"

    while IFS= read -r -d '' entry; do
        relative=${entry#"$stage/"}
        if contains_manifest_control "$relative"; then
            die "manifest_control_character"
        fi
        if [[ -L "$entry" ]]; then
            read_symlink_target "$entry"
            if contains_manifest_control "$SYMLINK_TARGET"; then
                die "manifest_control_character"
            fi
        fi
    done < <(
        find "$stage" -mindepth 1 -maxdepth 1 \( -type f -o -type l \) -print0 | LC_ALL=C sort -z
    )
}

require_exact_origin_runpath() {
    local dynamic_output="$1"
    local runpath_count
    local runpath_line
    if grep -F '(RPATH)' <<<"$dynamic_output" >/dev/null; then
        die "origin_runpath_invalid"
    fi
    runpath_count=$(grep -cF '(RUNPATH)' <<<"$dynamic_output" || true)
    [[ "$runpath_count" == "1" ]] || die "origin_runpath_invalid"
    runpath_line=$(grep -F '(RUNPATH)' <<<"$dynamic_output")
    grep -Eq '^[^[]*\(RUNPATH\)[^[]*\[\$ORIGIN\][[:space:]]*$' <<<"$runpath_line" || \
        die "origin_runpath_invalid"
}

cleanup() {
    local status=$?
    if [[ -n "${BUILD_DIR:-}" && -e "$BUILD_DIR" ]]; then
        rm -rf -- "$BUILD_DIR"
    fi
    if [[ -n "${STAGE_DIR:-}" && -e "$STAGE_DIR" ]]; then
        rm -rf -- "$STAGE_DIR"
    fi
    return "$status"
}

main() {
while (($#)); do
    case "$1" in
        --source-dir)
            (($# >= 2)) || die "missing_source_dir"
            SOURCE_DIR="$2"
            shift 2
            ;;
        --output-dir)
            (($# >= 2)) || die "missing_output_dir"
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            usage
            die "unknown_argument"
            ;;
    esac
done

[[ -n "$SOURCE_DIR" && -n "$OUTPUT_DIR" ]] || {
    usage
    die "required_argument_missing"
}

for required_command in git realpath dirname cmake find sort readlink sha256sum stat \
    cp mv rm grep readelf ldd; do
    command -v "$required_command" >/dev/null 2>&1 || die "tool_unavailable:${required_command}"
done
[[ -x "$NVCC" && ! -L "$NVCC" ]] || die "nvcc_unavailable"

SOURCE_ROOT=$(canonical_existing_dir "$SOURCE_ROOT")
SOURCE_DIR=$(canonical_existing_dir "$SOURCE_DIR")
INCUMBENT_DIR=$(canonical_existing_dir "$INCUMBENT_DIR")
CUDA_ROOT=$(canonical_existing_dir "$CUDA_ROOT")
CUDA_LIBRARY_ROOT=$(canonical_existing_dir "$CUDA_LIBRARY_ROOT")
[[ "$CUDA_LIBRARY_ROOT" == "$CUDA_ROOT/targets/x86_64-linux/lib" ]] || \
    die "cuda_library_root_mismatch"
for cuda_library in libcudart.so.13 libcublas.so.13 libcublasLt.so.13; do
    [[ -f "$CUDA_LIBRARY_ROOT/$cuda_library" ]] || die "cuda_library_unavailable"
done
OUTPUT_DIR=$(canonical_future_path "$OUTPUT_DIR")
[[ "$OUTPUT_DIR" == "$EXPECTED_OUTPUT_DIR" ]] || die "unexpected_output_path"
path_is_within "$SOURCE_DIR" "$SOURCE_ROOT" || die "unexpected_source_path"
[[ "$SOURCE_DIR" != "$SOURCE_ROOT" ]] || die "unexpected_source_path"

BUILD_DIR="${OUTPUT_DIR}.build"
STAGE_DIR="${OUTPUT_DIR}.stage"
BUILD_DIR=$(canonical_future_path "$BUILD_DIR")
STAGE_DIR=$(canonical_future_path "$STAGE_DIR")
refuse_existing_path "$OUTPUT_DIR"
refuse_existing_path "$BUILD_DIR"
refuse_existing_path "$STAGE_DIR"
require_pairwise_disjoint "$SOURCE_DIR" "$BUILD_DIR" "$STAGE_DIR" "$OUTPUT_DIR" "$INCUMBENT_DIR"

origin=$(git -C "$SOURCE_DIR" remote get-url origin)
case "$origin" in
    "$OFFICIAL_ORIGIN_HTTPS" | "$OFFICIAL_ORIGIN_SSH") ;;
    *) die "untrusted_source_origin" ;;
esac

head_commit=$(git -C "$SOURCE_DIR" rev-parse --verify HEAD)
tag_commit=$(git -C "$SOURCE_DIR" rev-parse --verify "refs/tags/${TAG}^{commit}")
short_commit=$(git -C "$SOURCE_DIR" rev-parse --short HEAD)
exact_tag=$(git -C "$SOURCE_DIR" describe --exact-match --tags HEAD)
[[ "$head_commit" == "$COMMIT" ]] || die "source_commit_mismatch"
[[ "$tag_commit" == "$COMMIT" ]] || die "source_tag_commit_mismatch"
[[ ${#short_commit} -ge 7 && "$COMMIT" == "$short_commit"* ]] || \
    die "source_short_commit_mismatch"
[[ "$exact_tag" == "$TAG" ]] || die "source_tag_mismatch"
[[ -z "$(git -C "$SOURCE_DIR" status --porcelain=v1 --untracked-files=all)" ]] || \
    die "source_tree_dirty"
require_source_generated_residue_absent "$SOURCE_DIR"

nvcc_version=$("$NVCC" --version 2>&1)
[[ "$nvcc_version" == *"release 13.2,"* && "$nvcc_version" == *"V13.2."* ]] || \
    die "nvcc_version_mismatch"

trap cleanup EXIT
mkdir -- "$BUILD_DIR"

cmake_args=(
    -S "$SOURCE_DIR"
    -B "$BUILD_DIR"
    -G Ninja
    -DCMAKE_BUILD_TYPE=Release
    "-DCMAKE_CUDA_COMPILER=${NVCC}"
    "-DCUDAToolkit_ROOT=${CUDA_ROOT}"
    -DGGML_CUDA=ON
    -DGGML_VULKAN=OFF
    -DGGML_CUDA_NCCL=OFF
    -DBUILD_SHARED_LIBS=ON
    -DGGML_BACKEND_DL=ON
    -DGGML_NATIVE=OFF
    -DGGML_CPU_ALL_VARIANTS=ON
    -DCMAKE_CUDA_ARCHITECTURES=89
    '-DCMAKE_INSTALL_RPATH=$ORIGIN'
    -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON
    -DFETCHCONTENT_FULLY_DISCONNECTED=ON
    -DLLAMA_BUILD_UI=OFF
    -DLLAMA_USE_PREBUILT_UI=OFF
)
cmake "${cmake_args[@]}"
cmake --build "$BUILD_DIR" --parallel
require_source_generated_residue_absent "$SOURCE_DIR"

BUILD_BIN_DIR="${BUILD_DIR}/bin"
[[ -d "$BUILD_BIN_DIR" && ! -L "$BUILD_BIN_DIR" ]] || die "build_bin_unavailable"
mkdir -- "$STAGE_DIR"
output_device=$(stat -c '%d' -- "$(dirname -- "$OUTPUT_DIR")")
stage_device=$(stat -c '%d' -- "$STAGE_DIR")
[[ "$output_device" == "$stage_device" ]] || die "cross_filesystem_stage"
cp -a -- "${BUILD_BIN_DIR}/." "$STAGE_DIR/"

[[ -x "$STAGE_DIR/llama-server" && ! -L "$STAGE_DIR/llama-server" ]] || \
    die "server_binary_unavailable"
[[ -z "$(find "$STAGE_DIR" -mindepth 1 -maxdepth 1 -type d -print -quit)" ]] || \
    die "nonflat_bundle"
[[ -n "$(find "$STAGE_DIR" -mindepth 1 -maxdepth 1 -name 'libggml-cuda.so*' -print -quit)" ]] || \
    die "cuda_backend_unavailable"
[[ -z "$(find "$STAGE_DIR" -mindepth 1 -maxdepth 1 -name 'libggml-vulkan.so*' -print -quit)" ]] || \
    die "vulkan_backend_present"
validate_staged_symlinks "$STAGE_DIR"
validate_manifest_inputs "$STAGE_DIR"

sanitized_candidate() {
    env -i \
        LC_ALL=C \
        HOME=/nonexistent \
        PATH="${CUDA_ROOT}/bin:/usr/bin:/bin" \
        LD_LIBRARY_PATH="$STAGE_DIR:$CUDA_LIBRARY_ROOT" \
        CUDA_VISIBLE_DEVICES=0 \
        GGML_VK_VISIBLE_DEVICES="" \
        "$@"
}

version_output=$(sanitized_candidate "$STAGE_DIR/llama-server" --version 2>&1)
grep -Fx -- "version: ${VERSION} (${short_commit})" <<<"$version_output" >/dev/null || \
    die "server_version_mismatch"
help_output=$(sanitized_candidate "$STAGE_DIR/llama-server" --help 2>&1)
for feature in --alias --ctx-size --parallel --n-gpu-layers -fa --cache-type-k \
    --cache-type-v --spec-type draft-mtp --spec-draft-n-max --kv-unified -fit; do
    grep -F -- "$feature" <<<"$help_output" >/dev/null || die "feature_unavailable:${feature}"
done

elf_count=0
while IFS= read -r -d '' artifact; do
    if env -i LC_ALL=C PATH=/usr/bin:/bin readelf -h -- "$artifact" >/dev/null 2>&1; then
        ((elf_count += 1))
        dynamic_output=$(env -i LC_ALL=C PATH=/usr/bin:/bin readelf -d -- "$artifact")
        require_exact_origin_runpath "$dynamic_output"
        link_output=$(env -i \
            LC_ALL=C \
            PATH=/usr/bin:/bin \
            LD_LIBRARY_PATH="$STAGE_DIR:$CUDA_LIBRARY_ROOT" \
            CUDA_VISIBLE_DEVICES=0 \
            GGML_VK_VISIBLE_DEVICES="" \
            ldd "$artifact" 2>&1)
        if grep -F -- "$INCUMBENT_DIR" <<<"${dynamic_output}"$'\n'"${link_output}" >/dev/null; then
            die "incumbent_dependency_detected"
        fi
        if grep -F -- "$FLOATING_CUDA_ROOT/" <<<"${dynamic_output}"$'\n'"${link_output}" >/dev/null; then
            die "floating_cuda_dependency_detected"
        fi
        if grep -F "not found" <<<"$link_output" >/dev/null; then
            die "dependency_not_found"
        fi
        local_dependencies=$(grep -E 'lib(ggml|llama|mtmd)[^ ]*\.so' <<<"$link_output" || true)
        if [[ -n "$local_dependencies" ]] && \
            grep -vF -- "$STAGE_DIR/" <<<"$local_dependencies" >/dev/null; then
            die "noncandidate_dependency_detected"
        fi
        cuda_dependencies=$(grep -E 'lib(cudart|cublas|cublasLt)[^ ]*\.so' <<<"$link_output" || true)
        if [[ -n "$cuda_dependencies" ]] && \
            grep -vF -- "$CUDA_LIBRARY_ROOT/" <<<"$cuda_dependencies" >/dev/null; then
            die "nonpinned_cuda_dependency_detected"
        fi
    fi
done < <(find "$STAGE_DIR" -mindepth 1 -maxdepth 1 -type f -print0 | LC_ALL=C sort -z)
((elf_count > 0)) || die "elf_bundle_empty"

MANIFEST_TMP="${STAGE_DIR}/${MANIFEST_NAME}.tmp"
(
    cd "$STAGE_DIR"
    export LC_ALL=C
    while IFS= read -r -d '' entry; do
        relative=${entry#./}
        if [[ -L "$entry" ]]; then
            read_symlink_target "$entry"
            target="$SYMLINK_TARGET"
            target_digest=$(printf '%s' "$target" | sha256sum)
            target_digest=${target_digest%% *}
            printf 'L\t%s\t%s\t%s\n' "$target_digest" "$relative" "$target"
        elif [[ -f "$entry" ]]; then
            file_digest=$(sha256sum -- "$entry")
            file_digest=${file_digest%% *}
            file_bytes=$(stat -c '%s' -- "$entry")
            printf 'F\t%s\t%s\t%s\n' "$file_digest" "$file_bytes" "$relative"
        else
            die "unsupported_manifest_entry"
        fi
    done < <(
        find . -mindepth 1 -maxdepth 1 \( -type f -o -type l \) \
            ! -name "$MANIFEST_NAME" ! -name "${MANIFEST_NAME}.tmp" -print0 | sort -z
    )
) >"$MANIFEST_TMP"
[[ -s "$MANIFEST_TMP" ]] || die "manifest_empty"
mv -- "$MANIFEST_TMP" "$STAGE_DIR/$MANIFEST_NAME"
[[ -z "$(find "$STAGE_DIR" -mindepth 1 -maxdepth 1 -name '*.tmp' -print -quit)" ]] || \
    die "temporary_artifact_present"

mv -T --no-clobber -- "$STAGE_DIR" "$OUTPUT_DIR"
[[ ! -e "$STAGE_DIR" && -d "$OUTPUT_DIR" ]] || die "publish_collision"
STAGE_DIR=""
printf 'candidate bundle published: %s\n' "$OUTPUT_DIR"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
