import 'package:flutter/material.dart';
import '../../services/api/api_service.dart';
import '../../models/market_regime.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';

class MarketRegimesScreen extends StatefulWidget {
  const MarketRegimesScreen({super.key});

  @override
  State<MarketRegimesScreen> createState() => _MarketRegimesScreenState();
}

class _MarketRegimesScreenState extends State<MarketRegimesScreen> {
  final ApiService _apiService = ApiService();
  late Future<MarketRegimeListResponse> _regimeFuture;

  @override
  void initState() {
    super.initState();
    _fetchData();
  }

  void _fetchData() {
    setState(() {
      _regimeFuture = _apiService.getMarketRegimes();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchData();
    try {
      await _regimeFuture;
    } catch (_) {}
  }

  // ---- Color / Icon Helpers ----

  Color _getRegimeColor(MarketRegime regime) {
    switch (regime) {
      case MarketRegime.TRENDING_BULLISH:
      case MarketRegime.BREAKOUT:
        return AppColors.success;
      case MarketRegime.TRENDING_BEARISH:
      case MarketRegime.REVERSAL:
        return AppColors.error;
      case MarketRegime.RANGING:
      case MarketRegime.LOW_VOLATILITY:
        return AppColors.info;
      case MarketRegime.HIGH_VOLATILITY:
      case MarketRegime.UNCERTAIN:
        return AppColors.warning;
    }
  }

  Color _getStrengthColor(RegimeStrength strength) {
    switch (strength) {
      case RegimeStrength.VERY_WEAK:
      case RegimeStrength.WEAK:
        return AppColors.error;
      case RegimeStrength.MODERATE:
        return AppColors.warning;
      case RegimeStrength.STRONG:
      case RegimeStrength.VERY_STRONG:
        return AppColors.success;
    }
  }

  Color _getConfidenceColor(RegimeConfidence conf) {
    switch (conf) {
      case RegimeConfidence.LOW:
        return AppColors.error;
      case RegimeConfidence.MEDIUM:
        return AppColors.warning;
      case RegimeConfidence.HIGH:
      case RegimeConfidence.VERY_HIGH:
        return AppColors.success;
    }
  }

  Color _getBiasColor(RecommendationBias bias) {
    switch (bias) {
      case RecommendationBias.BUY_BIAS:
        return AppColors.success;
      case RecommendationBias.SELL_BIAS:
        return AppColors.error;
      case RecommendationBias.NEUTRAL:
        return AppColors.info;
      case RecommendationBias.WAIT:
        return AppColors.warning;
    }
  }

  String _formatTime(DateTime dt) {
    final local = dt.toLocal();
    final h = local.hour.toString().padLeft(2, '0');
    final m = local.minute.toString().padLeft(2, '0');
    final s = local.second.toString().padLeft(2, '0');
    return '$h:$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Market Regime Intelligence'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _fetchData,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _handleRefresh,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16.0),
          child: FutureBuilder<MarketRegimeListResponse>(
            future: _regimeFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return Column(
                  children: const [
                    PlaceholderCard(height: 160),
                    SizedBox(height: 16),
                    PlaceholderCard(height: 400),
                  ],
                );
              } else if (snapshot.hasError) {
                return AppCard(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Failed to load Market Regimes',
                          style: TextStyle(
                            color: AppColors.error,
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          snapshot.error.toString().replaceAll('Exception: ', ''),
                          style: const TextStyle(color: AppColors.textSecondary),
                        ),
                        const SizedBox(height: 12),
                        ElevatedButton(
                          onPressed: _fetchData,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                );
              } else if (snapshot.hasData) {
                final response = snapshot.data!;
                final summary = response.summary;
                final sorted = List<MarketRegimeReport>.from(response.reports)
                  ..sort((a, b) => b.generatedAt.compareTo(a.generatedAt)); // latest first

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // 1. Summary Card
                    _buildSummaryCard(summary),
                    const SizedBox(height: 24),

                    // 2. Regime Cards
                    const Text(
                      'Market Regime Analysis',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 12),
                    if (sorted.isEmpty)
                      const AppCard(
                        child: Center(
                          child: Padding(
                            padding: EdgeInsets.all(16.0),
                            child: Text('No regime reports generated yet.', style: TextStyle(color: AppColors.textSecondary)),
                          ),
                        ),
                      )
                    else
                      ...sorted.map((r) => Padding(
                            padding: const EdgeInsets.only(bottom: 16),
                            child: _buildRegimeCard(r),
                          )),

                    const SizedBox(height: 12),
                    _buildMetadataFooter(sorted),
                    const SizedBox(height: 20),
                  ],
                );
              }
              return const SizedBox.shrink();
            },
          ),
        ),
      ),
    );
  }

  // ---- Summary Card ----

  Widget _buildSummaryCard(MarketRegimeSummary summary) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFF00BCD4).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.explore, color: Color(0xFF00BCD4), size: 24),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  'Historical Classifications',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 16,
            runSpacing: 16,
            children: [
              _buildStatItem('Total', summary.totalReports.toString(), AppColors.textPrimary),
              _buildStatItem('Bullish', summary.bullishCount.toString(), AppColors.success),
              _buildStatItem('Bearish', summary.bearishCount.toString(), AppColors.error),
              _buildStatItem('Ranging', summary.rangingCount.toString(), AppColors.info),
              _buildStatItem('High Vol', summary.highVolatilityCount.toString(), const Color(0xFF9C27B0)),
              _buildStatItem('Breakout', summary.breakoutCount.toString(), const Color(0xFFFF9800)),
              _buildStatItem('Reversal', summary.reversalCount.toString(), AppColors.error),
              _buildStatItem('Uncertain', summary.uncertainCount.toString(), AppColors.warning),
            ],
          ),
        ],
      ),
    );
  }

  // ---- Regime Card ----

  Widget _buildRegimeCard(MarketRegimeReport r) {
    final regimeColor = _getRegimeColor(r.regime);
    final strengthColor = _getStrengthColor(r.strength);
    final confColor = _getConfidenceColor(r.confidence);
    final biasColor = _getBiasColor(r.recommendation.bias);

    // Sort factors by weight descending
    final factors = List<RegimeFactor>.from(r.factors)..sort((a, b) => b.weight.compareTo(a.weight));

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header: ID and Badges
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Report: ${r.id}',
                style: const TextStyle(fontSize: 12, color: AppColors.textTertiary, fontWeight: FontWeight.bold),
              ),
              Row(
                children: [
                  _buildBadge(r.strength.name, strengthColor),
                  const SizedBox(width: 6),
                  _buildBadge('Conf: ${r.confidence.name}', confColor),
                ],
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Regime Title
          Row(
            children: [
              Icon(Icons.radar, color: regimeColor, size: 24),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  r.regime.name.replaceAll('_', ' '),
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: regimeColor),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Overall Score Gauge
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Overall Regime Score', style: TextStyle(color: AppColors.textSecondary, fontSize: 13)),
              Text('${r.overallScore.toStringAsFixed(1)} / 100',
                  style: TextStyle(fontWeight: FontWeight.bold, color: regimeColor, fontSize: 14)),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: (r.overallScore / 100.0).clamp(0.0, 1.0),
              backgroundColor: AppColors.background,
              valueColor: AlwaysStoppedAnimation<Color>(regimeColor),
              minHeight: 10,
            ),
          ),
          const SizedBox(height: 20),

          // Factor Breakdown
          const Text('Factor Breakdown', style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 14)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: AppColors.background, borderRadius: BorderRadius.circular(8)),
            child: Column(
              children: factors.map((f) => Padding(
                padding: const EdgeInsets.only(bottom: 8.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('${f.name} (${(f.weight * 100).toStringAsFixed(0)}%)', style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                        Text(f.score.toStringAsFixed(1), style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 12)),
                      ],
                    ),
                    const SizedBox(height: 4),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(2),
                      child: LinearProgressIndicator(
                        value: (f.score / 100.0).clamp(0.0, 1.0),
                        backgroundColor: AppColors.surfaceLight,
                        valueColor: const AlwaysStoppedAnimation<Color>(AppColors.primary),
                        minHeight: 4,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(f.description, style: const TextStyle(color: AppColors.textTertiary, fontSize: 10)),
                  ],
                ),
              )).toList(),
            ),
          ),
          const SizedBox(height: 20),

          // Recommendation Panel
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: biasColor.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: biasColor.withValues(alpha: 0.4)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.lightbulb, color: biasColor, size: 18),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        r.recommendation.title,
                        style: TextStyle(color: biasColor, fontWeight: FontWeight.bold, fontSize: 14),
                      ),
                    ),
                    _buildBadge(r.recommendation.bias.name, biasColor),
                  ],
                ),
                const SizedBox(height: 8),
                Text(r.recommendation.description, style: const TextStyle(color: AppColors.textPrimary, fontSize: 13)),
                const SizedBox(height: 12),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Best Strategies', style: TextStyle(color: AppColors.success, fontWeight: FontWeight.bold, fontSize: 12)),
                          const SizedBox(height: 4),
                          if (r.recommendation.bestStrategies.isEmpty)
                            const Text('None', style: TextStyle(color: AppColors.textTertiary, fontSize: 11))
                          else
                            ...r.recommendation.bestStrategies.map((s) => Row(
                              children: [
                                const Icon(Icons.check, color: AppColors.success, size: 12),
                                const SizedBox(width: 4),
                                Expanded(child: Text(s, style: const TextStyle(color: AppColors.textSecondary, fontSize: 11))),
                              ],
                            )),
                        ],
                      ),
                    ),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Avoid Strategies', style: TextStyle(color: AppColors.error, fontWeight: FontWeight.bold, fontSize: 12)),
                          const SizedBox(height: 4),
                          if (r.recommendation.avoidStrategies.isEmpty)
                            const Text('None', style: TextStyle(color: AppColors.textTertiary, fontSize: 11))
                          else
                            ...r.recommendation.avoidStrategies.map((s) => Row(
                              children: [
                                const Icon(Icons.close, color: AppColors.error, size: 12),
                                const SizedBox(width: 4),
                                Expanded(child: Text(s, style: const TextStyle(color: AppColors.textSecondary, fontSize: 11))),
                              ],
                            )),
                        ],
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // Market Snapshot
          const Text('Market Snapshot', style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary, fontSize: 14)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.background,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.surfaceLight),
            ),
            child: Column(
              children: [
                _buildSnapshotRow('Trend', r.snapshot.trend, 'Volatility', r.snapshot.volatility),
                const Divider(height: 16, color: AppColors.surfaceLight),
                _buildSnapshotRow('Spread', r.snapshot.spread.toStringAsFixed(1), 'Session', r.snapshot.session),
                const Divider(height: 16, color: AppColors.surfaceLight),
                _buildSnapshotRow('Sentiment', r.snapshot.marketSentiment, 'Fear/Greed', r.snapshot.fearGreed),
                const Divider(height: 16, color: AppColors.surfaceLight),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('News Impact', style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                    Text(r.snapshot.newsImpact, style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold, fontSize: 12)),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ---- Metadata Footer ----

  Widget _buildMetadataFooter(List<MarketRegimeReport> sorted) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        const Divider(color: AppColors.surfaceLight),
        const SizedBox(height: 4),
        Center(
          child: Text(
            'Pipeline Stage: MARKET_REGIME • Timeline Order: 8 • Engine v1.0.0',
            style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
          ),
        ),
        const SizedBox(height: 2),
        if (sorted.isNotEmpty)
          Center(
            child: Text(
              'Generated by Market Regime Intelligence Engine',
              style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
            ),
          ),
        const SizedBox(height: 2),
        Center(
          child: Text(
            'Refreshed at: ${_formatTime(DateTime.now())}',
            style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
          ),
        ),
      ],
    );
  }

  // ---- Tiny helpers ----

  Widget _buildStatItem(String label, String value, Color color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
        const SizedBox(height: 4),
        Text(value, style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: color)),
      ],
    );
  }

  Widget _buildBadge(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color),
      ),
      child: Text(
        text,
        style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 10),
      ),
    );
  }

  Widget _buildSnapshotRow(String l1, String v1, String l2, String v2) {
    return Row(
      children: [
        Expanded(
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(l1, style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
              Text(v1, style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold, fontSize: 12)),
            ],
          ),
        ),
        const SizedBox(width: 16),
        Container(width: 1, height: 14, color: AppColors.surfaceLight),
        const SizedBox(width: 16),
        Expanded(
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(l2, style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
              Text(v2, style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold, fontSize: 12)),
            ],
          ),
        ),
      ],
    );
  }
}
