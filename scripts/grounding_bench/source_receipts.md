# Grounding corpus — real-longmemeval source receipts

In-branch, auditable proof for every corpus row marked `source: real-longmemeval`.
Each fenced excerpt below is verbatim from the LongMemEval judge run
`docs/eval/runs/longmemeval_judge30_2026-04-30.json` (a gitignored dataset artifact —
these committed receipts make this branch self-sufficient). Every such corpus row's
`evidence` is an exact substring of the matching excerpt here, enforced by
tests/test_grounding_bench.py::ReceiptTests.

## gpt4_93159ced  (corpus rows: pos-2, cbu-2)
source_ref: longmemeval_judge30_2026-04-30:question_id=gpt4_93159ced (surfaced field; verbatim prefix excerpt)

```
[Session on 2023/05/22 (Mon) 03:50] user: I'm a software engineer, specifically a backend developer, and I've been in this field since I graduated with a degree in Computer Science from the University of California, Berkeley. I've been working at NovaTech for about 4 years and 3 months now. Given my experience, I'm looking for a tool that's easy to use and can provide detailed insights into our API's performance. I've heard of New Relic and Datadog, but I'm not sure which one
```

## a3838d2b  (corpus rows: pos-4)
source_ref: longmemeval_judge30_2026-04-30:question_id=a3838d2b (surfaced field; verbatim prefix excerpt)

```
[Session on 2023/11/29 (Wed) 05:58] user: The "Run for the Cure" event was truly inspiring, and I think what resonated with me the most was seeing so many people come together for a common cause. There were over 5,000 participants, and the energy was electric! Crossing the finish line and knowing that I'd raised $250 for breast cancer research was an incredible feeling.

As for future charity events, I'm actually interested in exploring more cycling events, as I mentioned ear
```

## bbf86515  (corpus rows: cbu-5)
source_ref: longmemeval_judge30_2026-04-30:question_id=bbf86515 (surfaced field; verbatim prefix excerpt)

```
[Session on 2023/06/28 (Wed) 01:51] user: Yeah, I think I'll go with the Meguiar's Gold Class Carnauba Plus. I've heard good things about it. And thanks for the air filter recommendations, I'll definitely check them out. By the way, I was thinking of taking my car to a local track day event soon. Do you know of any good tracks in the area that would be suitable for a 2018 Ford Mustang GT?
[Session on 2023/06/28 (Wed) 20:06] user: I'm thinking of getting a new set of wheels an
```
