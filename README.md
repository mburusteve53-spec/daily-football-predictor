# Daily Football 5-Odds Predictor v2

Phone-friendly Streamlit app for exploring current soccer odds across available leagues.

## Important limitations
- Live odds require a The Odds API key and depend on provider coverage and quota.
- Probabilities are market-implied estimates, adjusted to remove margin within the same market/bookmaker. This is not a proven independent prediction model.
- This version does not independently fetch injury news, confirmed lineups, or recent team form. Check these manually before betting.
- Combined chance multiplies individual probabilities and assumes independence, which may be imperfect.
- The app never guarantees a win and reports when no combination meets the target/rules.

## Run on a phone
Deploy this app to Streamlit Community Cloud from a GitHub repository, then open its URL on your Android phone.

## Setup
1. Create an API key with The Odds API: https://the-odds-api.com/
2. Upload `app.py` and `requirements.txt` to a GitHub repository.
3. Deploy `app.py` using Streamlit Community Cloud.
4. Enter the API key in the app when prompted. Do not publish your key in a public repository.
5. Select bookmaker region, odds target and minimum selection probability, then tap **Fetch upcoming football odds**.

## Confidence labels
- High: >= 75% market-implied probability
- Medium: 60% to 74.9%
- Lower: < 60%

These are transparent bands, not calibrated confidence intervals or guarantees.

## Markets
The app requests head-to-head match result (`h2h`) and total goals (`totals`). Availability varies by league, region, bookmaker and API plan. Double chance and draw-no-bet are not assumed to be available from this endpoint.
