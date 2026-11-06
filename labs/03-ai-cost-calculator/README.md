# Lab 03: AI cost calculator

**Result:** one command turns "tokens per request, price, volume" into cost per request, per 1,000 requests, per day and per month, for several models side by side.

## The problem

"How much will the AI feature cost?" is the first question a client's finance or procurement team asks, and the usual answer is a guess. LLM providers price input and output tokens separately, per million tokens, and output is often several times more expensive. Small changes (a longer system prompt, a chattier answer, ten times the traffic) move the bill by orders of magnitude, and nobody sees it until the invoice arrives.

## What this lab does

`cost_calc.py` applies one formula:

```
cost per request = input_tokens x input_price / 1M + output_tokens x output_price / 1M
cost per period  = cost per request x requests per day x days
```

- Prices are **inputs**, passed as `--model name:input_price:output_price` (USD per 1M tokens). Nothing is hard-coded, because prices change.
- Repeat `--model` to compare models on the same workload.
- Money maths uses `Decimal`, so there is no floating-point drift.
- Bad input (negative numbers, text instead of a price) prints an error and exits with code 2 instead of producing a wrong number.

The tests include a hand-checked example: 1,000 input + 500 output tokens at $3 / $15 per 1M is $0.0105 per request, $3,150 for 10,000 requests a day over 30 days. No API calls, no network, no secrets.

## Run it

```bash
pip install -r requirements.txt
python cost_calc.py --input-tokens 1000 --output-tokens 500 \
  --requests-per-day 10000 \
  --model small:0.15:0.60 --model large:3:15

pytest -q
```

Output:

```
| Model | Per request | Per 1k requests | Per day | Per 30 days |
|-------|-------------|-----------------|---------|-------------|
| small | $0.000450   | $0.45           | $4.50   | $135.00     |
| large | $0.010500   | $10.50          | $105.00 | $3,150.00   |
```

The model names and prices above are example inputs. Use your provider's current price page.

## Why it matters to a business

It turns model choice into a budget conversation: in this example the large model costs 23x more per month for the same traffic. That number decides whether the feature ships on the large model, ships on the small one, or needs an eval to prove the large one is worth it. It also makes the levers visible: trimming 500 tokens from a prompt or capping answer length shows up directly in the monthly line.

## Trade-off

It is a flat estimate: one average request shape, steady daily volume. It ignores prompt caching discounts, batch pricing, retries, tool-call round trips and peak-hour spikes. That keeps it a 30-second answer for a first conversation; for a real forecast, feed it measured token counts from logs (planned in Lab 19) instead of guesses.
