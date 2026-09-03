"""
Falcon Risk Management Engine
Institutional-grade risk evaluation for trade setups.
"""
import time
from typing import Optional, List
from datetime import datetime, timezone
from app.schemas.risk_models import RiskDecision, RiskAssessment, RiskStatistics
from app.schemas.signal_models import TradeSetup
from app.schemas.signal_settings import SignalSettings
from app.schemas.decision_models import AIDecisionResult
from app.schemas.trend_models import TrendResult
from app.schemas.confluence_models import MultiTimeframeConfluenceResult


class RiskManagementEngine:
    """
    Risk Management Engine - Falcon's final gatekeeper.
    
    Evaluates every generated trade setup and determines whether the trade
    satisfies Falcon's risk policy before it can be presented as an approved signal.
    """
    
    # Correlation groups (instruments that move together)
    CORRELATION_GROUPS = {
        "USD_PAIRS": ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCHF", "USDCAD"],
        "COMMODITIES": ["XAUUSD", "XAGUSD", "USOIL", "UKOIL"],
        "JPY_PAIRS": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"],
        "EUR_PAIRS": ["EURUSD", "EURGBP", "EURJPY", "EURAUD", "EURCHF"]
    }
    
    def __init__(self, settings: Optional[SignalSettings] = None):
        """Initialize the risk management engine."""
        # Use provided settings or default
        self.settings = settings if settings else SignalSettings()
        
        # Statistics
        self._total_assessments = 0
        self._approved_count = 0
        self._approved_with_warning_count = 0
        self._rejected_count = 0
        self._total_risk_score = 0.0
        self._total_risk_percent = 0.0
        self._total_rr = 0.0
        self._total_assessment_time = 0.0
        self._rejection_reasons = {}
        
        # Track daily risk (simplified - in production would use persistent storage)
        self._daily_risk_accumulated = 0.0
        
        # Track open positions (simplified - in production would use persistent storage)
        self._open_positions = []
    
    def evaluate(
        self,
        trade_setup: TradeSetup,
        ai_decision: Optional[AIDecisionResult] = None,
        trend_result: Optional[TrendResult] = None,
        mt_confluence_result: Optional[MultiTimeframeConfluenceResult] = None,
        account_balance: float = 100000.0,
        position_size: float = 1.0
    ) -> RiskAssessment:
        """
        Evaluate trade setup against risk policy.
        
        Args:
            trade_setup: Trade setup to evaluate
            ai_decision: AI decision result
            trend_result: Trend analysis result
            mt_confluence_result: Multi-timeframe confluence result
            account_balance: Account balance for risk calculation
            position_size: Position size for risk calculation
            
        Returns:
            RiskAssessment with complete risk evaluation
        """
        start_time = time.time()
        
        reasons = []
        warnings = []
        risk_score = 0.0
        
        # 1. Risk/Reward Validation
        rr_valid, rr_warning = self._validate_risk_reward(trade_setup.riskRewardRatio)
        if not rr_valid:
            reasons.append(f"RR below minimum ({trade_setup.riskRewardRatio:.2f} < {self.settings.minimum_rr})")
            risk_score += 30
        elif rr_warning:
            warnings.append(f"RR below preferred ({trade_setup.riskRewardRatio:.2f} < {self.settings.preferred_rr})")
            risk_score += 10
        else:
            reasons.append(f"RR acceptable ({trade_setup.riskRewardRatio:.2f})")
        
        # 2. Stop Loss Distance Validation
        sl_valid, sl_distance = self._validate_stop_loss_distance(
            trade_setup.entryPrice, trade_setup.stopLoss, getattr(trade_setup, "symbol", "EURUSD")
        )
        if not sl_valid:
            reasons.append(f"Stop loss distance exceeds maximum ({sl_distance:.2f} pips > {self.settings.maximum_stop_distance})")
            risk_score += 20
        else:
            reasons.append(f"Stop loss distance acceptable ({sl_distance:.2f} pips)")
        
        # 3. Signal Confidence Validation
        confidence_valid = self._validate_confidence(trade_setup.confidence)
        if not confidence_valid:
            reasons.append(f"Confidence below threshold ({trade_setup.confidence:.2f} < {self.settings.minimum_confidence})")
            risk_score += 15
        else:
            reasons.append(f"Confidence acceptable ({trade_setup.confidence:.2f})")
        
        # 4. AI Confidence Validation
        ai_confidence_valid = True
        if ai_decision:
            ai_confidence_valid = self._validate_ai_confidence(ai_decision.confidence)
            if not ai_confidence_valid:
                reasons.append(f"AI confidence below threshold ({ai_decision.confidence:.2f} < {self.settings.minimum_ai_confidence})")
                risk_score += 15
            else:
                reasons.append(f"AI confidence acceptable ({ai_decision.confidence:.2f})")
        
        # 5. Signal Score Validation (from AI decision)
        signal_score_valid = True
        if ai_decision and ai_decision.signalScore:
            signal_score_valid = self._validate_signal_score(ai_decision.signalScore)
            if not signal_score_valid:
                reasons.append(f"Signal score below threshold ({ai_decision.signalScore:.2f} < {self.settings.minimum_signal_score})")
                risk_score += 15
            else:
                reasons.append(f"Signal score acceptable ({ai_decision.signalScore:.2f})")
        
        # 6. Multi-Timeframe Validation
        confluence_valid = True
        if mt_confluence_result:
            confluence_valid = self._validate_confluence(mt_confluence_result.overallConfluenceScore)
            if not confluence_valid:
                reasons.append(f"Confluence below threshold ({mt_confluence_result.overallConfluenceScore:.2f} < {self.settings.minimum_confluence})")
                risk_score += 15
            else:
                reasons.append(f"Confluence acceptable ({mt_confluence_result.overallConfluenceScore:.2f})")
        
        # 7. Trend Validation
        trend_valid = True
        if trend_result and not self.settings.allow_counter_trend_trades:
            trend_valid = self._validate_trend(trade_setup.signalType.value, trend_result.direction.value)
            if not trend_valid:
                reasons.append(f"Counter-trend trade not allowed ({trade_setup.signalType.value} vs {trend_result.direction.value})")
                risk_score += 20
            else:
                reasons.append(f"Trend alignment confirmed")
        
        # 8. Position Risk Calculation
        risk_percent = self._calculate_position_risk(
            trade_setup.entryPrice, trade_setup.stopLoss, account_balance, position_size
        )
        
        # 9. Daily Risk Validation
        daily_risk_valid = self._validate_daily_risk(risk_percent)
        if not daily_risk_valid:
            reasons.append(f"Daily risk exceeded ({risk_percent:.2f}% + {self._daily_risk_accumulated:.2f}% > {self.settings.maximum_daily_risk_percent}%)")
            risk_score += 25
        else:
            reasons.append(f"Daily risk acceptable ({risk_percent:.2f}%)")
        
        # 10. Portfolio Exposure Validation
        portfolio_exposure = self._calculate_portfolio_exposure(risk_percent)
        portfolio_valid = self._validate_portfolio_exposure(portfolio_exposure)
        if not portfolio_valid:
            reasons.append(f"Portfolio exposure exceeded ({portfolio_exposure:.2f}% > {self.settings.maximum_open_risk_percent}%)")
            risk_score += 25
        else:
            reasons.append(f"Portfolio exposure acceptable ({portfolio_exposure:.2f}%)")
        
        # 11. Correlation Risk Validation
        correlation_level = self._determine_correlation_level(trade_setup.symbol)
        correlation_valid = self._validate_correlation(trade_setup.symbol)
        if not correlation_valid:
            reasons.append(f"Too many correlated positions ({correlation_level})")
            risk_score += 20
        else:
            reasons.append(f"Correlation risk acceptable ({correlation_level})")
        
        # Determine overall decision
        if risk_score >= 50:
            decision = RiskDecision.REJECTED
            approved = False
        elif risk_score >= 25:
            decision = RiskDecision.APPROVED_WITH_WARNING
            approved = True
        else:
            decision = RiskDecision.APPROVED
            approved = True
        
        # Update statistics
        execution_time = (time.time() - start_time) * 1000
        self._total_assessments += 1
        self._total_risk_score += risk_score
        self._total_risk_percent += risk_percent
        self._total_rr += trade_setup.riskRewardRatio
        self._total_assessment_time += execution_time
        
        if decision == RiskDecision.APPROVED:
            self._approved_count += 1
            # Add to open positions and daily risk if approved
            self._open_positions.append(trade_setup.symbol)
            self._daily_risk_accumulated += risk_percent
        elif decision == RiskDecision.APPROVED_WITH_WARNING:
            self._approved_with_warning_count += 1
            # Add to open positions and daily risk if approved
            self._open_positions.append(trade_setup.symbol)
            self._daily_risk_accumulated += risk_percent
        else:
            self._rejected_count += 1
            # Track rejection reason
            if reasons:
                reason_key = reasons[0].split(":")[0] if ":" in reasons[0] else reasons[0]
                self._rejection_reasons[reason_key] = self._rejection_reasons.get(reason_key, 0) + 1
        
        # Create result
        result = RiskAssessment(
            signalId=trade_setup.signalId,
            symbol=trade_setup.symbol,
            timeframe=trade_setup.timeframe,
            decision=decision,
            overallRiskScore=risk_score,
            riskPercent=risk_percent,
            rr=trade_setup.riskRewardRatio,
            dailyExposure=self._daily_risk_accumulated,
            portfolioExposure=portfolio_exposure,
            correlationLevel=correlation_level,
            approved=approved,
            reasons=reasons,
            warnings=warnings,
            assessedAt=datetime.now(timezone.utc)
        )
        
        return result
    
    def _validate_risk_reward(self, rr: float) -> tuple[bool, bool]:
        """Validate risk/reward ratio."""
        if rr < self.settings.minimum_rr:
            return False, False
        elif rr < self.settings.preferred_rr:
            return True, True
        else:
            return True, False
    
    def _validate_stop_loss_distance(self, entry_price: float, stop_loss: float, symbol: str = "EURUSD") -> tuple[bool, float]:
        """Validate stop loss distance in pips with asset-specific calculation."""
        distance = abs(entry_price - stop_loss)
        symbol_upper = str(symbol).upper().replace("/", "").replace("_", "")
        if "XAU" in symbol_upper or "GOLD" in symbol_upper:
            pips = distance * 10.0
            max_sl = 300.0  # Gold allows up to 300 pips ($30)
        elif "JPY" in symbol_upper:
            pips = distance * 100.0
            max_sl = 150.0  # JPY allows up to 150 pips (1.50 yen)
        else:
            pips = distance * 10000.0
            max_sl = self.settings.maximum_stop_distance
        return pips <= max_sl, pips
    
    def _validate_confidence(self, confidence: float) -> bool:
        """Validate signal confidence."""
        return confidence >= self.settings.minimum_confidence
    
    def _validate_ai_confidence(self, ai_confidence: float) -> bool:
        """Validate AI decision confidence."""
        return ai_confidence >= self.settings.minimum_ai_confidence
    
    def _validate_signal_score(self, signal_score: float) -> bool:
        """Validate signal score."""
        return signal_score >= self.settings.minimum_signal_score
    
    def _validate_confluence(self, confluence_score: float) -> bool:
        """Validate multi-timeframe confluence."""
        return confluence_score >= self.settings.minimum_confluence
    
    def _validate_trend(self, signal_type: str, trend_direction: str) -> bool:
        """Validate trend alignment (reject counter-trend if not allowed)."""
        if self.settings.allow_counter_trend_trades:
            return True
        
        if signal_type == "BUY" and trend_direction == "BULLISH":
            return True
        elif signal_type == "SELL" and trend_direction == "BEARISH":
            return True
        else:
            return False
    
    def _calculate_position_risk(
        self, entry_price: float, stop_loss: float, account_balance: float, position_size: float
    ) -> float:
        """Calculate position risk as percentage of account."""
        risk_per_unit = abs(entry_price - stop_loss)
        total_risk = risk_per_unit * position_size
        risk_percent = (total_risk / account_balance) * 100
        return round(risk_percent, 2)
    
    def _validate_daily_risk(self, risk_percent: float) -> bool:
        """Validate daily risk limit."""
        return (self._daily_risk_accumulated + risk_percent) <= self.settings.maximum_daily_risk_percent
    
    def _calculate_portfolio_exposure(self, risk_percent: float) -> float:
        """Calculate total portfolio exposure."""
        return round(self._daily_risk_accumulated + risk_percent, 2)
    
    def _validate_portfolio_exposure(self, portfolio_exposure: float) -> bool:
        """Validate portfolio exposure limit."""
        return portfolio_exposure <= self.settings.maximum_open_risk_percent
    
    def _determine_correlation_level(self, symbol: str) -> str:
        """Determine correlation level for a symbol."""
        # Count correlated positions
        correlated_count = 0
        
        for group in self.CORRELATION_GROUPS.values():
            if symbol in group:
                for position in self._open_positions:
                    if position in group:
                        correlated_count += 1
                break
        
        if correlated_count == 0:
            return "LOW"
        elif correlated_count <= self.settings.maximum_correlated_positions:
            return "MEDIUM"
        else:
            return "HIGH"
    
    def _validate_correlation(self, symbol: str) -> bool:
        """Validate correlation risk."""
        correlation_level = self._determine_correlation_level(symbol)
        return correlation_level != "HIGH"
    
    def get_statistics(self) -> dict:
        """Get engine statistics."""
        avg_risk_score = (
            self._total_risk_score / self._total_assessments
            if self._total_assessments > 0
            else 0.0
        )
        
        avg_risk_percent = (
            self._total_risk_percent / self._total_assessments
            if self._total_assessments > 0
            else 0.0
        )
        
        avg_rr = (
            self._total_rr / self._total_assessments
            if self._total_assessments > 0
            else 0.0
        )
        
        avg_assessment_time = (
            self._total_assessment_time / self._total_assessments
            if self._total_assessments > 0
            else 0.0
        )
        
        return {
            'totalAssessments': self._total_assessments,
            'approvedCount': self._approved_count,
            'approvedWithWarningCount': self._approved_with_warning_count,
            'rejectedCount': self._rejected_count,
            'averageRiskScore': round(avg_risk_score, 2),
            'averageRiskPercent': round(avg_risk_percent, 2),
            'averageRR': round(avg_rr, 2),
            'averageAssessmentTime': round(avg_assessment_time, 2),
            'rejectionReasons': self._rejection_reasons
        }
    
    def reset_statistics(self) -> None:
        """Reset engine statistics."""
        self._total_assessments = 0
        self._approved_count = 0
        self._approved_with_warning_count = 0
        self._rejected_count = 0
        self._total_risk_score = 0.0
        self._total_risk_percent = 0.0
        self._total_rr = 0.0
        self._total_assessment_time = 0.0
        self._rejection_reasons = {}
        self._daily_risk_accumulated = 0.0
        self._open_positions = []
