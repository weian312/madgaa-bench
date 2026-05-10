# datasets/

## Internal de-id prompts (v2)
- `prompts/task_A_soap_en.txt`, `task_B_ddx_en.txt`, `task_C_drug_zh.txt`, `task_D_icd_zh.txt` — at the top level of the repo, used in v2 baseline numbers.

## MTSamples public corpus (v2.1 cross-validation)

`mtsamples.csv` is the source corpus of ~5,000 transcribed clinical reports (Apache-2.0). **Not committed** (17 MB, available upstream). To recreate:

```bash
mkdir -p datasets
curl -sL https://huggingface.co/datasets/harishnair04/mtsamples/resolve/main/mtsamples.csv \
  -o datasets/mtsamples.csv
```

Then sample task prompts:

```bash
python scripts/sample_mtsamples.py --n-soap 30 --n-ddx 30 --seed 42
```

This emits:
- `mtsamples_sampled/soap_en/000.txt`–`029.txt` — SOAP summarisation prompts
- `mtsamples_sampled/ddx_en/000.txt`–`029.txt` — DDx reasoning prompts
- `mtsamples_sampled/index.jsonl` — id → source_row, specialty, sample_name, prompt_hash

The 60 sampled prompt files **are committed** so anyone can reproduce our exact MTSamples bench without re-running the sampler. `index.jsonl` lets you trace each sampled prompt back to its MTSamples row.

## Why two prompt sets?

- **v2 internal prompts** = 1 hand-crafted representative case per task. Useful for headline NT$ comparison; suspect-able as cherry-picked.
- **v2.1 MTSamples** = 30 randomly-sampled real clinical transcriptions per task. Provides distribution + confidence interval. Cross-validates v2 numbers against public data.

The blog post's headline numbers are from v2 internal. v2.1 (with MTSamples) will be the addendum that shows whether the headline holds up across realistic case variation.
