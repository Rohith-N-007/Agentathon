# First Review Pitch: Agentathon 2026 (Education track)

## 90-second script (split between 2 speakers)

**Speaker 1: problem and solution (45s)**
"Students preparing for placements practise on LeetCode and Codeforces. When a submission fails, they read the editorial, fix that one problem and move on. Existing tools like LeetCode tags, LCPath and LeetCoach track *topics* and solve history. They tell you 'you're weak at graphs', not *which reasoning mistake* you keep making. In our survey of 15 students, 11 (73%) said they repeat the same mistake across multiple submissions.

Our product is an AI coach agent. It reads a failed submission, forms competing hypotheses about the cause, *proves* the cause by running two versions of the code in a sandbox, remembers it in a weakness fingerprint, and plans daily practice that targets it."

**Speaker 2: agentic angle, scope, ask (45s)**
"Why agentic: every step depends on what the previous tool returned. The agent must execute code to learn what is true, it retries or abstains when the experiment is inconclusive, and it keeps memory across sessions. One LLM call can't run an experiment, and a static app can't pick the next test.

In 24 hours we are building: Python-only, paste-in submissions, one problem family with three different failure causes, the full loop with a visible trace, a fingerprint dashboard, a prediction gate and a measured-result chart. Live LeetCode/Codeforces integration is out of scope for now.

Known risks: mutations that don't compile or don't change behaviour, sandbox safety, vague labels. Our mitigations are retry with the error (max 2), output-equality checks, timeout and memory limits, and abstaining when unsure.

What we'd like feedback on: is the experiment-based diagnosis the right thing to polish, and is anything must-have missing?"

## One-line hook
> Other tools tell you what you got wrong. Ours shows you why, by running the experiment.

## Likely reviewer questions and answers

| Question | Answer |
|---|---|
| How is this different from asking ChatGPT? | ChatGPT explains in text. We run a counterfactual experiment, show measured numbers, and keep a persistent fingerprint across sessions. |
| How do you know the diagnosis is right? | A hypothesis is confirmed only if A and A′ give identical outputs but measurably different behaviour (operation count). Otherwise we abstain and say we're unsure. |
| What if the code has several bugs? | One hypothesis at a time, ranked by cost and information gain. Memory is updated only on conclusive results. |
| Is the sandbox safe? | Separate process with a hard timeout and a memory watchdog; Docker Desktop with no network is a stretch goal. |
| What if the LLM produces a bad mutation? | Compile check, one-decision-change check (diff size), output-equality check. Retry with the error up to 2 times. |
| How will you measure impact? | Pilot with 10 students; measure repeat-mistake rate before and after. |
| Why trust a 15-student survey? | We don't claim it is representative. It is a small peer sample that motivated the problem; the pilot is how we validate. |
| Can it scale? | A few LLM calls per analysis; the sandbox is cheap. Cost per user is low (estimate, to be measured in the pilot). |
| What does "mastered" mean? | A clean, optimized solve with no error of that type, after which the fingerprint score decays and the review interval grows (SM-2). |

## Deck gaps to fix before final submission
1. Team name is blank. Pick one.
2. "What didn't work" says NA. Add 2-3 real learnings from the hackathon (e.g. the mutation that changed outputs, op-counting issues).
3. Demo evidence and Links say NA. Add the GitHub repo and a demo video link.
4. Replace wireframes with real screenshots.
5. Add a line defining how the fingerprint score is computed.
6. Be honest that the survey is a small peer sample.
7. References slide lists the Python `resource` module (Unix-only). Replace it with psutil (psutil.readthedocs.io) since we run on Windows. Also change "Sandbox: subprocess with CPU/memory limits" on the tech stack slide to "subprocess with timeout and psutil memory watchdog".
