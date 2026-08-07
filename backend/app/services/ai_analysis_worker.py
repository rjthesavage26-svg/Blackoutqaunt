from pathlib import Path
from typing import Any

from app.models.ai_analysis import SavedTradeAnalysis, TradeAnalysisDraft
from app.services.ai_analysis_repository import AIAnalysisRepository


class AIAnalysisWorker:
    # This worker is intentionally deterministic for now. It behaves like an
    # "AI coach" by turning stored trade data and known strategy rules into a
    # beginner-friendly explanation, without calling an external AI service.
    def __init__(self, database_path: Path) -> None:
        self.repository = AIAnalysisRepository(database_path)

    def analyze_saved_trade(self, trade_id: int) -> SavedTradeAnalysis | None:
        # This method is safe to run in the background after a webhook is saved.
        # It can also be called again later to regenerate a fresh analysis row.
        trade = self.repository.get_trade_by_id(trade_id)
        if trade is None:
            return None

        analysis = self._build_analysis(trade)
        return self.repository.save_analysis(analysis)

    def _build_analysis(self, trade: dict[str, Any]) -> TradeAnalysisDraft:
        checks = self._evaluate_strategy_rules(trade)
        passed_checks = sum(1 for check in checks if check["status"] == "pass")
        failed_checks = sum(1 for check in checks if check["status"] == "fail")
        unknown_checks = sum(1 for check in checks if check["status"] == "unknown")
        known_checks = passed_checks + failed_checks

        # Confidence measures how complete and supportive the stored data is. It
        # is not a prediction of profit; it is a quality score for the setup.
        if known_checks == 0:
            confidence_score = 0
        else:
            rule_score = passed_checks / len(checks)
            missing_data_penalty = unknown_checks * 6
            confidence_score = max(0, min(100, round(rule_score * 100) - missing_data_penalty))

        trade_grade = self._grade_from_score(confidence_score, failed_checks, unknown_checks)

        return TradeAnalysisDraft(
            trade_id=trade["id"],
            trade_grade=trade_grade,
            confidence_score=confidence_score,
            plain_english_explanation=self._build_plain_english_explanation(trade, checks),
            why_the_trade_qualified=self._build_qualification_text(trade, checks),
            risk_factors=self._build_risk_factors(trade, checks),
            watch_after_entry=self._build_watch_after_entry(trade),
            educational_summary=self._build_educational_summary(trade, trade_grade, confidence_score),
            source_data=trade,
        )

    def _evaluate_strategy_rules(self, trade: dict[str, Any]) -> list[dict[str, str]]:
        action = trade["action"]
        is_long = action == "BUY"
        side_label = "long" if is_long else "short"

        return [
            self._check_value("Ticker must be QQQ", trade["ticker"] == "QQQ"),
            self._check_value("Action must be BUY or SELL", action in {"BUY", "SELL"}),
            self._check_comparison(
                f"Price must be {'above' if is_long else 'below'} VWAP for a {side_label} setup",
                trade["price"],
                trade["vwap"],
                ">" if is_long else "<",
            ),
            self._check_comparison(
                f"EMA 50 must be {'above' if is_long else 'below'} EMA 200 for a {side_label} setup",
                trade["ema50"],
                trade["ema200"],
                ">" if is_long else "<",
            ),
            self._check_comparison(
                f"Price must be {'above opening range high' if is_long else 'below opening range low'}",
                trade["price"],
                trade["opening_range_high"] if is_long else trade["opening_range_low"],
                ">" if is_long else "<",
            ),
            self._check_volume(trade),
            self._check_stop_loss(trade, is_long),
            self._check_take_profit(trade, is_long),
            self._check_reward_risk(trade),
        ]

    def _check_value(self, label: str, passed: bool) -> dict[str, str]:
        return {
            "rule": label,
            "status": "pass" if passed else "fail",
            "detail": "Confirmed from stored trade data." if passed else "Stored trade data does not satisfy this rule.",
        }

    def _check_comparison(
        self,
        label: str,
        first_value: float | None,
        second_value: float | None,
        operator: str,
    ) -> dict[str, str]:
        if first_value is None or second_value is None:
            return {
                "rule": label,
                "status": "unknown",
                "detail": "This cannot be determined because one or more required values were not stored.",
            }

        passed = first_value > second_value if operator == ">" else first_value < second_value
        return {
            "rule": label,
            "status": "pass" if passed else "fail",
            "detail": f"Stored values: {first_value} {operator} {second_value}.",
        }

    def _check_volume(self, trade: dict[str, Any]) -> dict[str, str]:
        if trade["volume"] is None or trade["average_volume"] is None:
            return {
                "rule": "Volume must be at least 1.5 times the 20-bar average volume",
                "status": "unknown",
                "detail": "This cannot be determined because volume or average_volume was not stored.",
            }

        required_volume = trade["average_volume"] * 1.5
        passed = trade["volume"] >= required_volume
        return {
            "rule": "Volume must be at least 1.5 times the 20-bar average volume",
            "status": "pass" if passed else "fail",
            "detail": f"Stored values: volume {trade['volume']} vs required {required_volume}.",
        }

    def _check_stop_loss(self, trade: dict[str, Any], is_long: bool) -> dict[str, str]:
        if trade["stop_loss"] is None:
            return {
                "rule": "Every trade must have a stop loss",
                "status": "unknown",
                "detail": "This cannot be determined because stop_loss was not stored.",
            }

        passed = trade["stop_loss"] < trade["price"] if is_long else trade["stop_loss"] > trade["price"]
        return {
            "rule": "Every trade must have a stop loss on the correct side of entry",
            "status": "pass" if passed else "fail",
            "detail": f"Stored values: entry {trade['price']} and stop_loss {trade['stop_loss']}.",
        }

    def _check_take_profit(self, trade: dict[str, Any], is_long: bool) -> dict[str, str]:
        if trade["take_profit"] is None:
            return {
                "rule": "Every trade must have a take profit",
                "status": "unknown",
                "detail": "This cannot be determined because take_profit was not stored.",
            }

        passed = trade["take_profit"] > trade["price"] if is_long else trade["take_profit"] < trade["price"]
        return {
            "rule": "Every trade must have a take profit on the correct side of entry",
            "status": "pass" if passed else "fail",
            "detail": f"Stored values: entry {trade['price']} and take_profit {trade['take_profit']}.",
        }

    def _check_reward_risk(self, trade: dict[str, Any]) -> dict[str, str]:
        if trade["stop_loss"] is None or trade["take_profit"] is None:
            return {
                "rule": "Reward/risk must be at least 2:1",
                "status": "unknown",
                "detail": "This cannot be determined because stop_loss or take_profit was not stored.",
            }

        risk = abs(trade["price"] - trade["stop_loss"])
        reward = abs(trade["take_profit"] - trade["price"])
        if risk == 0:
            return {
                "rule": "Reward/risk must be at least 2:1",
                "status": "fail",
                "detail": "Stored stop_loss equals entry price, so risk is zero and the setup is invalid.",
            }

        reward_risk = reward / risk
        reward_risk_passes = reward_risk >= 2 or abs(reward_risk - 2) <= 1e-9
        return {
            "rule": "Reward/risk must be at least 2:1",
            "status": "pass" if reward_risk_passes else "fail",
            "detail": f"Stored reward/risk is {reward_risk:.2f}:1.",
        }

    def _grade_from_score(self, confidence_score: int, failed_checks: int, unknown_checks: int) -> str:
        if failed_checks >= 2:
            return "F"
        if failed_checks == 1:
            return "D"
        if confidence_score >= 90 and unknown_checks == 0:
            return "A"
        if confidence_score >= 75:
            return "B"
        if confidence_score >= 60:
            return "C"
        if confidence_score >= 40:
            return "D"
        return "F"

    def _build_plain_english_explanation(self, trade: dict[str, Any], checks: list[dict[str, str]]) -> str:
        side = "long" if trade["action"] == "BUY" else "short"
        unknown_count = sum(1 for check in checks if check["status"] == "unknown")
        failed_count = sum(1 for check in checks if check["status"] == "fail")

        explanation = (
            f"This was stored as a {side} paper trade on {trade['ticker']} at {trade['price']}. "
            "The analysis compares the stored alert data against the Blackout Quant rules: VWAP, EMA trend, opening range, volume, stop loss, and reward/risk."
        )

        if failed_count:
            explanation += f" {failed_count} required rule check failed based on stored data."
        if unknown_count:
            explanation += f" {unknown_count} rule check cannot be determined because the needed values were not stored."

        return explanation

    def _build_qualification_text(self, trade: dict[str, Any], checks: list[dict[str, str]]) -> str:
        confirmed = [check["rule"] for check in checks if check["status"] == "pass"]
        unavailable = [check["rule"] for check in checks if check["status"] == "unknown"]

        text = "Confirmed qualification factors: " + ("; ".join(confirmed) if confirmed else "none from the stored data.")
        if unavailable:
            text += " Cannot be determined from stored data: " + "; ".join(unavailable) + "."
        text += " Reason codes received: " + ", ".join(trade["reason_codes"]) + "."
        return text

    def _build_risk_factors(self, trade: dict[str, Any], checks: list[dict[str, str]]) -> str:
        failed_or_unknown = [
            f"{check['rule']} ({check['detail']})"
            for check in checks
            if check["status"] in {"fail", "unknown"}
        ]

        if trade["atr"] is None:
            failed_or_unknown.append("ATR cannot be reviewed because atr was not stored.")

        return "; ".join(failed_or_unknown) if failed_or_unknown else "No rule-based risk factors were found in the stored data."

    def _build_watch_after_entry(self, trade: dict[str, Any]) -> str:
        watch_items = [
            "Watch whether price respects VWAP after entry.",
            "Watch whether the EMA 50/EMA 200 trend relationship remains supportive.",
            "Watch whether volume continues to support the move instead of fading.",
        ]

        if trade["stop_loss"] is None:
            watch_items.append("Stop loss cannot be monitored from stored data because stop_loss was unavailable.")
        else:
            watch_items.append(f"Watch the stop loss level at {trade['stop_loss']}.")

        if trade["take_profit"] is None:
            watch_items.append("Take profit cannot be monitored from stored data because take_profit was unavailable.")
        else:
            watch_items.append(f"Watch the take profit level at {trade['take_profit']}.")

        return " ".join(watch_items)

    def _build_educational_summary(self, trade: dict[str, Any], grade: str, confidence_score: int) -> str:
        return (
            f"Educational summary: this paper trade received grade {grade} with confidence {confidence_score}/100. "
            "A higher grade means the stored data more completely matched the Blackout Quant setup rules. "
            "This is not financial advice and does not predict whether the trade will be profitable."
        )
