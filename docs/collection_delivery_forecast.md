# Collection delivery forecast

## Scope

Party-to-office receipt only, grouped by collection and master collection.
The model uses the same authorization and selected filters as the report.
No supplier, stage, shop-receipt or user identity is inferred as a predictor.
No new database columns or dependencies are required.

## Bayesian model

Receipt duration T given rate lambda follows Exponential(lambda).
Prior: lambda ~ Gamma(shape=1, rate=1 day). This is a fixed, explicit
regularizing prior, not a prior fitted from the same observations twice.
It has no finite prior mean duration. Predictions are withheld until at
least 5 valid completed observations and positive total exposure exist.
This threshold is a display safeguard, not evidence of calibration.

For D completed receipts with summed duration S, and pending exposure C:

    likelihood(lambda) proportional to lambda^D * exp(-lambda * (S + C))
    posterior shape a = 1 + D
    posterior rate  b = 1 + S + C
    predictive survival P(T > t | data) = (b / (b + t))^a
    predictive mean = b / (a - 1)
    predictive quantile q(p) = b * ((1 - p)^(-1/a) - 1)

The displayed 90% predictive interval uses q(0.05), q(0.95). It is for
an individual new receipt, not a credible interval for the mean.

For an existing pending record with elapsed age c and target d:

    P(exceed target | data, still pending) = (b / (b + max(d-c, 0)))^a

Its survival through age c is already in C. Applying survival conditioning
a second time would double-count it. At/past the target, a still-pending
continuous-time receipt has breach probability 1. The observed overdue
count uses the report's strict age > target rule.
Expected breach count sums individual probabilities; the displayed percent
is their count-weighted mean, excluding missing/negative targets.
Those excluded records still contribute pending exposure and are identified
in the UI. No pending records / no valid targets produce N/A, not zero risk.

The remaining-time distribution is the same predictive distribution for
all existing pending records under the constant-hazard assumption. Elapsed
age changes target-breach probability but not expected remaining days.

## Data and limitations

- Completed observations require order <= office receipt <= observation date.
- Pending observations require no office receipt and order <= observation date.
- Dates use the Asia/Kolkata calendar. Negative/missing durations and future
  receipts are excluded, not converted into completed records or zero days.
- Same-day completion has zero calendar-day exposure. Date-only inputs are an
  approximation to continuous time; intervals are not hour-accurate estimates.
- Every snapshot row is an observation. Do not claim barcode or order-level
  independence without validating duplicates and shared order/batch effects.
- Full filtered group statistics are calculated before pagination. No page-
  dependent prior or cross-user unfiltered baseline enters the forecast.
- Right censoring assumes pending really means awaiting receipt, not cancellation,
  missing updates, lost records, or other competing outcomes.
- Constant hazard, exchangeability, independence, and stationarity are assumptions,
  not established facts about this business. Filters may create selection bias.
- Shape/rate defaults are model choices. Review prior sensitivity for small groups.

## Validation status

Experimental, NOT historically validated. Unit tests verify formulas, censoring,
target boundaries, missing data, interval ordering and numerical behavior. They
do not prove predictive accuracy. Do not label the output "High Confidence".

Before operational reliance, run time-based backtests: train using only events
known at each historical cutoff, censor unfinished observations at that cutoff,
and score later outcomes with sufficient follow-up. Check predictive 90% coverage,
remaining-day errors, Brier score/calibration by horizon, group and sample size;
compare against historical medians and target-only rules. Avoid current-state
filters that reveal future outcomes. Use archived snapshots where records or
attributes can change, and do not score still-unresolved outcomes as on-time.
If the exponential assumption fails, evaluate a Bayesian Weibull or piecewise
hazard model rather than silently adjusting these probabilities.

Reference: NIST Gamma-Exponential Bayesian reliability model:
https://www.itl.nist.gov/div898/handbook/apr/section4/apr46.htm
