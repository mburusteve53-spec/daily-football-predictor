import os
import math
from datetime import datetime, timezone
from itertools import combinations

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Daily 5-Odds Predictor", page_icon="⚽", layout="centered")
st.title("⚽ Daily Football 5-Odds Predictor")
st.caption("Version 2 • phone-friendly • live odds only when an API key is supplied")

with st.expander("How the score works", expanded=False):
    st.markdown("""
    - **Live odds:** fetched from The Odds API; no odds are invented.
    - **Estimated probability:** market-implied probability adjusted to remove the bookmaker margin where opposing outcomes are available.
    - **Confidence label:** based on that estimate only: High ≥ 75%, Medium 60–74.9%, Lower < 60%.
    - **Accumulator chance:** multiplies individual probabilities and assumes selections are independent. This can be inaccurate, especially for related markets.
    - **Limit:** this version does not independently verify injuries, lineups, or team form. Treat those as a final manual check.
    """)

api_key = st.text_input("The Odds API key", value=os.getenv("ODDS_API_KEY", ""),
                        type="password", help="Get a key from theoddsapi.com. It is not stored by this app.")
regions = st.selectbox("Bookmaker region", ["uk", "eu", "us", "au"], index=0)
target = st.number_input("Target combined odds", min_value=2.0, max_value=20.0, value=5.0, step=0.25)
band = st.slider("Allowed range around target", min_value=0.25, max_value=2.0, value=0.5, step=0.25)
max_legs = st.slider("Maximum selections", min_value=2, max_value=8, value=5)
min_prob = st.slider("Minimum estimated chance per selection", min_value=0.40, max_value=0.90, value=0.60, step=0.01)
sports_filter = st.selectbox("Fixture scope", ["All available soccer leagues", "Popular leagues only"])
refresh = st.button("Fetch upcoming football odds", type="primary", use_container_width=True)

@st.cache_data(ttl=300, show_spinner=False)
def fetch_sports(key):
    r = requests.get("https://api.the-odds-api.com/v4/sports/", params={"apiKey": key}, timeout=25)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=180, show_spinner=False)
def fetch_odds(key, sport_key, region):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    r = requests.get(url, params={"apiKey": key, "regions": region, "markets": "h2h,totals",
                                  "oddsFormat": "decimal", "dateFormat": "iso"}, timeout=25)
    r.raise_for_status()
    return r.json()

def confidence(p):
    return "High" if p >= 0.75 else ("Medium" if p >= 0.60 else "Lower")

def normalize_probs(outcomes):
    vals = [1.0 / float(o["price"]) for o in outcomes if float(o.get("price", 0)) > 1]
    total = sum(vals)
    if not vals or total <= 0:
        return {}
    return {o["name"]: (1.0 / float(o["price"])) / total
            for o in outcomes if float(o.get("price", 0)) > 1}

def extract_candidates(events):
    candidates = []
    for ev in events:
        home, away = ev.get("home_team", ""), ev.get("away_team", "")
        if not home or not away:
            continue
        best = {}
        for book in ev.get("bookmakers", []):
            markets = {m.get("key"): m for m in book.get("markets", [])}
            h2h = markets.get("h2h")
            if h2h:
                probs = normalize_probs(h2h.get("outcomes", []))
                for outcome in h2h.get("outcomes", []):
                    name, price = outcome.get("name"), outcome.get("price")
                    p = probs.get(name)
                    if not name or not price or price <= 1 or not p:
                        continue
                    key = (ev.get("id"), "h2h", name)
                    if key not in best or price > best[key]["odds"]:
                        best[key] = {"event_id": ev.get("id"), "match": f"{home} vs {away}",
                                     "market": f"Match result: {name}", "selection": name,
                                     "odds": float(price), "prob": float(p),
                                     "kickoff": ev.get("commence_time", ""),
                                     "bookmaker": book.get("title", "Unknown")}
            totals = markets.get("totals")
            if totals:
                grouped = {}
                for outcome in totals.get("outcomes", []):
                    point = outcome.get("point")
                    if point is not None:
                        grouped.setdefault(point, []).append(outcome)
                for point, pair in grouped.items():
                    probs = normalize_probs(pair)
                    for outcome in pair:
                        name, price = outcome.get("name"), outcome.get("price")
                        p = probs.get(name)
                        if not name or not price or price <= 1 or not p:
                            continue
                        key = (ev.get("id"), "totals", point, name)
                        if key not in best or price > best[key]["odds"]:
                            best[key] = {"event_id": ev.get("id"), "match": f"{home} vs {away}",
                                         "market": f"Total goals {name} {point}", "selection": f"{name} {point}",
                                         "odds": float(price), "prob": float(p),
                                         "kickoff": ev.get("commence_time", ""),
                                         "bookmaker": book.get("title", "Unknown")}
        candidates.extend(best.values())
    return candidates

def choose_slips(candidates, target, band, max_legs, min_prob):
    pool = [c for c in candidates if c["prob"] >= min_prob and c["odds"] > 1]
    pool = sorted(pool, key=lambda x: x["prob"], reverse=True)[:32]
    found = []
    for n in range(2, min(max_legs, len(pool)) + 1):
        for combo in combinations(pool, n):
            if len({c["event_id"] for c in combo}) != len(combo):
                continue
            total_odds = math.prod(c["odds"] for c in combo)
            if target - band <= total_odds <= target + band:
                chance = math.prod(c["prob"] for c in combo)
                found.append({"selections": combo, "odds": total_odds, "chance": chance, "legs": n})
    found.sort(key=lambda x: (-x["chance"], x["legs"], abs(x["odds"] - target)))
    return found

if refresh:
    if not api_key.strip():
        st.error("Enter your The Odds API key first. No live odds have been fetched.")
    else:
        try:
            with st.spinner("Loading available soccer leagues and odds..."):
                sports = fetch_sports(api_key.strip())
                soccer = [s for s in sports if s.get("key", "").startswith("soccer_") and s.get("active")]
                if sports_filter == "Popular leagues only":
                    preferred = ("soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a",
                                 "soccer_germany_bundesliga", "soccer_france_ligue_one",
                                 "soccer_uefa_champs_league")
                    soccer = [s for s in soccer if s.get("key") in preferred]
                all_events, errors = [], []
                progress = st.progress(0)
                for i, league in enumerate(soccer):
                    try:
                        all_events.extend(fetch_odds(api_key.strip(), league["key"], regions))
                    except requests.RequestException as e:
                        errors.append(f"{league.get('title', league['key'])}: {e}")
                    progress.progress((i + 1) / max(1, len(soccer)))
                now = datetime.now(timezone.utc)
                upcoming, seen = [], set()
                for event in all_events:
                    try:
                        kickoff = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
                    except Exception:
                        continue
                    if kickoff > now and event.get("id") not in seen:
                        upcoming.append(event)
                        seen.add(event.get("id"))
                st.session_state["candidates"] = extract_candidates(upcoming)
                st.session_state["event_count"] = len(upcoming)
                st.session_state["league_count"] = len(soccer)
                st.session_state["errors"] = errors
                st.session_state["loaded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except requests.RequestException as e:
            st.error(f"Live data request failed: {e}. Check the API key, quota, and internet connection.")
        except Exception as e:
            st.error(f"Could not process provider data: {e}")

if "candidates" in st.session_state:
    st.caption(f"Fetched at {st.session_state.get('loaded_at','unknown')} • "
               f"{st.session_state.get('event_count',0)} upcoming fixtures • "
               f"{st.session_state.get('league_count',0)} leagues checked")
    if st.session_state.get("errors"):
        with st.expander("Some leagues could not be loaded"):
            st.write("\n".join(st.session_state["errors"][:20]))
    candidates = st.session_state["candidates"]
    if not candidates:
        st.warning("No usable upcoming odds were returned. This can happen when markets are unavailable.")
    else:
        df = pd.DataFrame([{"Kickoff (UTC)": c["kickoff"], "Match": c["match"],
                            "Selection": c["market"], "Odds": round(c["odds"], 2),
                            "Est. probability": f'{c["prob"]:.1%}', "Confidence": confidence(c["prob"]),
                            "Bookmaker": c["bookmaker"]} for c in candidates])
        st.subheader("Candidate selections")
        st.dataframe(df, use_container_width=True, hide_index=True)
        slips = choose_slips(candidates, float(target), float(band), int(max_legs), float(min_prob))
        st.subheader("Best combination near target odds")
        if not slips:
            st.info("No combination met your odds range and minimum probability. Do not force a slip; lower the target or wait for more markets.")
        else:
            best = slips[0]
            st.metric("Combined odds", f'{best["odds"]:.2f}')
            st.metric("Estimated chance all selections win", f'{best["chance"]:.2%}')
            st.caption(f'{best["legs"]} selections • model estimate, not a guarantee')
            for i, c in enumerate(best["selections"], 1):
                st.markdown(f"**{i}. {c['match']}**  \n{c['market']} • odds **{c['odds']:.2f}** • "
                            f"estimated chance **{c['prob']:.1%}** ({confidence(c['prob'])})  \n"
                            f"<small>Kickoff: {c['kickoff']} · price source: {c['bookmaker']}</small>",
                            unsafe_allow_html=True)
            st.warning("The accumulator chance multiplies market estimates and assumes independence. "
                       "It is not a calibrated forecast; manually check lineups, injuries, kickoff times and prices.")
            st.download_button("Download candidate selections CSV",
                               data=pd.DataFrame([{"match": c["match"], "market": c["market"],
                                                    "odds": c["odds"], "estimated_probability": c["prob"],
                                                    "kickoff": c["kickoff"], "bookmaker": c["bookmaker"]}
                                                   for c in best["selections"]]).to_csv(index=False),
                               file_name="daily_5_odds_shortlist.csv", mime="text/csv",
                               use_container_width=True)

st.divider()
st.caption("Responsible use: betting involves loss risk. Never stake money needed for essentials. A higher estimated probability does not mean positive expected value.")
