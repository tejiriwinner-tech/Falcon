import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../services/api/api_service.dart';
import '../../models/signal_candidate.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';
import '../../core/utils/price_formatter.dart';

class SignalCandidatesScreen extends StatefulWidget {
  const SignalCandidatesScreen({super.key});

  @override
  State<SignalCandidatesScreen> createState() => _SignalCandidatesScreenState();
}

class _SignalCandidatesScreenState extends State<SignalCandidatesScreen> {
  final ApiService _apiService = ApiService();
  late Future<SignalCandidateListResponse> _candidatesFuture;

  @override
  void initState() {
    super.initState();
    _fetchCandidates();
  }

  void _fetchCandidates() {
    setState(() {
      _candidatesFuture = _apiService.getSignalCandidates();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchCandidates();
    try {
      await _candidatesFuture;
    } catch (_) {}
  }

  String _formatRelativeTime(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.isNegative) return 'Just now';
    if (diff.inSeconds < 60) return '${diff.inSeconds}s ago';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return '${diff.inDays}d ago';
  }

  String _formatAbsoluteTime(DateTime dt) {
    final h = dt.hour.toString().padLeft(2, '0');
    final m = dt.minute.toString().padLeft(2, '0');
    final s = dt.second.toString().padLeft(2, '0');
    final ms = dt.millisecond.toString().padLeft(3, '0');
    return '$h:$m:$s.$ms';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Signal Candidates'),
        centerTitle: true,
      ),
      body: RefreshIndicator(
        onRefresh: _handleRefresh,
        color: AppColors.primary,
        child: FutureBuilder<SignalCandidateListResponse>(
          future: _candidatesFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  const PlaceholderCard(height: 100),
                  const SizedBox(height: 16),
                  ...List.generate(
                    3,
                    (_) => const Padding(
                      padding: EdgeInsets.only(bottom: 16),
                      child: PlaceholderCard(height: 250),
                    ),
                  ),
                ],
              );
            } else if (snapshot.hasError) {
              return Center(
                child: SingleChildScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(24.0),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.error_outline,
                          color: AppColors.error, size: 64),
                      const SizedBox(height: 16),
                      const Text(
                        'Failed to load candidates',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        snapshot.error.toString().replaceAll('Exception: ', ''),
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: AppColors.textSecondary),
                      ),
                      const SizedBox(height: 24),
                      ElevatedButton(
                        onPressed: _fetchCandidates,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.primary,
                          foregroundColor: Colors.black,
                          padding: const EdgeInsets.symmetric(
                              horizontal: 24, vertical: 12),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                ),
              );
            } else if (snapshot.hasData) {
              final response = snapshot.data!;
              final candidates = response.candidates;

              return ListView(
                padding: const EdgeInsets.all(16),
                physics: const AlwaysScrollableScrollPhysics(),
                children: [
                  _buildSummaryCard(candidates),
                  const SizedBox(height: 16),
                  if (candidates.isEmpty)
                    const Center(
                      child: Padding(
                        padding: EdgeInsets.all(40.0),
                        child: Text(
                          'No active candidates found',
                          style: TextStyle(color: AppColors.textSecondary),
                        ),
                      ),
                    )
                  else
                    ...candidates.map((cand) => _buildCandidateCard(cand)),
                ],
              );
            }
            return const SizedBox.shrink();
          },
        ),
      ),
    );
  }

  Widget _buildSummaryCard(List<SignalCandidate> candidates) {
    final total = candidates.length;
    final buyCount = candidates.where((c) => c.direction == CandidateDirection.buy).length;
    final sellCount = candidates.where((c) => c.direction == CandidateDirection.sell).length;
    final waitCount = candidates.where((c) => c.direction == CandidateDirection.wait).length;
    
    final averageConfidence = total > 0
        ? (candidates.map((c) => c.confidence).reduce((a, b) => a + b) / total).round()
        : 0;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Candidate Explorer Summary',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: AppColors.primary,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: AppColors.surfaceLight,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  'Total: $total',
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildSummaryStat('BUY', buyCount.toString(), AppColors.success),
              _buildSummaryStat('SELL', sellCount.toString(), AppColors.error),
              _buildSummaryStat('WAIT', waitCount.toString(), AppColors.warning),
              _buildSummaryStat('Avg Conf', '$averageConfidence%', AppColors.primary),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryStat(String label, String value, Color color) {
    return Column(
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 10, color: AppColors.textTertiary),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
      ],
    );
  }

  Widget _buildCandidateCard(SignalCandidate cand) {
    final isBuy = cand.direction == CandidateDirection.buy;
    final isSell = cand.direction == CandidateDirection.sell;
    
    Color directionColor;
    String directionText;
    if (isBuy) {
      directionColor = AppColors.success;
      directionText = '🟢 BUY';
    } else if (isSell) {
      directionColor = AppColors.error;
      directionText = '🔴 SELL';
    } else {
      directionColor = AppColors.warning;
      directionText = '🟡 WAIT';
    }

    Color statusColor;
    switch (cand.status) {
      case CandidateStatus.generated:
      case CandidateStatus.validated:
      case CandidateStatus.riskChecked:
      case CandidateStatus.executionReady:
      case CandidateStatus.approved:
        statusColor = AppColors.success;
        break;
      case CandidateStatus.waitingConfirmation:
        statusColor = AppColors.warning;
        break;
      case CandidateStatus.rejected:
        statusColor = AppColors.error;
        break;
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 16.0),
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: directionColor.withValues(alpha: 0.2),
            width: 1.5,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 1. Strategy Name & Version
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Row(
                children: [
                  const Icon(Icons.psychology, size: 14, color: AppColors.textTertiary),
                  const SizedBox(width: 4),
                  const Text(
                    'Strategy: ',
                    style: TextStyle(color: AppColors.textTertiary, fontSize: 12),
                  ),
                  Expanded(
                    child: GestureDetector(
                      onTap: () {
                        context.push('/strategies/${cand.strategyId}');
                      },
                      child: Text(
                        '${cand.strategyName} v${cand.strategyVersion}',
                        style: const TextStyle(
                          color: AppColors.primary,
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          decoration: TextDecoration.underline,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.05),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      '${cand.strategyGrade} (Score: ${cand.strategyScore})',
                      style: const TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            // 2, 3, 4. Symbol, Direction Badge, Status Badge
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 10),
              child: Row(
                children: [
                  Text(
                    cand.symbol,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: directionColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      directionText,
                      style: TextStyle(
                        color: directionColor,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                        letterSpacing: 0.8,
                      ),
                    ),
                  ),
                  const Spacer(),
                  // Status Badge
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: statusColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: statusColor.withValues(alpha: 0.2)),
                    ),
                    child: Text(
                      cand.status.toJson(),
                      style: TextStyle(
                        color: statusColor,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 4),

            // 5. Technical Confidence progress bar
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Text(
                        'Technical Confidence:',
                        style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(4),
                          child: LinearProgressIndicator(
                            value: cand.confidence / 100,
                            backgroundColor: AppColors.surfaceLight,
                            valueColor: AlwaysStoppedAnimation<Color>(
                              cand.confidence >= 80
                                  ? AppColors.success
                                  : (cand.confidence >= 60 ? AppColors.warning : AppColors.error),
                            ),
                            minHeight: 6,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        '${cand.confidence}%',
                        style: TextStyle(
                          color: cand.confidence >= 80
                              ? AppColors.success
                              : (cand.confidence >= 60 ? AppColors.warning : AppColors.error),
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  // Breakdown values wrap
                  Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    children: [
                      _buildBreakdownChip('Trend', cand.confidenceBreakdown.trendScore, 30),
                      _buildBreakdownChip('Strategy', cand.confidenceBreakdown.strategyScore, 25),
                      _buildBreakdownChip('Session', cand.confidenceBreakdown.sessionScore, 20),
                      _buildBreakdownChip('Sentiment', cand.confidenceBreakdown.sentimentScore, 15),
                      _buildBreakdownChip('News', cand.confidenceBreakdown.newsScore, 10),
                    ],
                  ),
                ],
              ),
            ),

            const SizedBox(height: 12),

            // 6. Execution Readiness progress bar
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  const Text(
                    'Execution Readiness:',
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: cand.readinessScore / 100,
                        backgroundColor: AppColors.surfaceLight,
                        valueColor: AlwaysStoppedAnimation<Color>(
                          cand.readinessScore >= 85
                              ? AppColors.success
                              : (cand.readinessScore >= 50 ? AppColors.warning : AppColors.error),
                        ),
                        minHeight: 6,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '${cand.readinessScore}%',
                    style: TextStyle(
                      color: cand.readinessScore >= 85
                          ? AppColors.success
                          : (cand.readinessScore >= 50 ? AppColors.warning : AppColors.error),
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 16),

            // 7. Entry / Stop Loss / Take Profit / Risk:Reward (Price Details row)
            Container(
              color: AppColors.surfaceLight.withValues(alpha: 0.3),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Row(
                children: [
                  _buildPriceItem('Entry', PriceFormatter.format(cand.symbol, cand.entryPrice), AppColors.textSecondary),
                  _buildPriceItem('SL', PriceFormatter.format(cand.symbol, cand.stopLoss), AppColors.error),
                  _buildPriceItem('TP', PriceFormatter.format(cand.symbol, cand.takeProfit), AppColors.success),
                  _buildPriceItem('Risk:Reward', '1:${cand.riskReward.toStringAsFixed(1)}', AppColors.primary),
                ],
              ),
            ),

            // 8. Market Snapshot Panel
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 6, 16, 4),
              child: Theme(
                data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                child: ExpansionTile(
                  title: const Row(
                    children: [
                      Icon(Icons.bar_chart, size: 16, color: AppColors.primary),
                      SizedBox(width: 6),
                      Text(
                        'Market Snapshot during evaluation',
                        style: TextStyle(color: AppColors.primary, fontSize: 12, fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  tilePadding: EdgeInsets.zero,
                  childrenPadding: const EdgeInsets.only(top: 8, bottom: 8),
                  minTileHeight: 32,
                  dense: true,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AppColors.surfaceLight.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: GridView.count(
                        crossAxisCount: 2,
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        crossAxisSpacing: 16,
                        mainAxisSpacing: 8,
                        childAspectRatio: 3.5,
                        children: [
                          _buildSnapshotItem('Trend', cand.marketSnapshot.trend),
                          _buildSnapshotItem('Volatility', cand.marketSnapshot.volatility),
                          _buildSnapshotItem('Session', cand.marketSnapshot.session),
                          _buildSnapshotItem('Spread', '${cand.marketSnapshot.spread.toStringAsFixed(2)} pips'),
                          _buildSnapshotItem('News Impact', cand.marketSnapshot.newsImpact),
                          _buildSnapshotItem('Sentiment', cand.marketSnapshot.marketSentiment),
                          _buildSnapshotItem('Confidence', '${cand.marketSnapshot.marketConfidence}%'),
                          _buildSnapshotItem('Data Age', '${cand.marketDataAgeSeconds}s'),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),

            // 9. Rejection / Verdict Reasons
            if (cand.reasons.isNotEmpty) ...[
              const Padding(
                padding: EdgeInsets.fromLTRB(16, 8, 16, 4),
                child: Text(
                  'Evaluation Findings',
                  style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                child: Column(
                  children: cand.reasons.map((reason) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(
                          reason.passed ? Icons.check_circle_outline : Icons.warning_amber_rounded,
                          color: reason.passed ? AppColors.success : AppColors.warning,
                          size: 14,
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                reason.title,
                                style: TextStyle(
                                  color: reason.passed ? AppColors.success : AppColors.warning,
                                  fontWeight: FontWeight.bold,
                                  fontSize: 11,
                                ),
                              ),
                              Text(
                                reason.description,
                                style: const TextStyle(
                                  color: AppColors.textSecondary,
                                  fontSize: 11,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  )).toList(),
                ),
              ),
            ],

            // 10. Conditions (Pass/Fail)
            if (cand.conditions.isNotEmpty) ...[
              const Padding(
                padding: EdgeInsets.fromLTRB(16, 12, 16, 4),
                child: Text(
                  'Validation Checklist',
                  style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                child: Column(
                  children: cand.conditions.map((cond) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(
                          cond.passed ? Icons.check_circle : Icons.cancel,
                          color: cond.passed ? AppColors.success : AppColors.error,
                          size: 14,
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: RichText(
                            text: TextSpan(
                              text: '${cond.title}: ',
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                                fontSize: 11,
                              ),
                              children: [
                                TextSpan(
                                  text: cond.description,
                                  style: const TextStyle(
                                    color: AppColors.textSecondary,
                                    fontWeight: FontWeight.normal,
                                    fontSize: 11,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  )).toList(),
                ),
              ),
            ],

            const Divider(color: AppColors.surfaceLight, height: 1),

            // 11. Footer / Generated Timestamp
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 14),
              child: Row(
                children: [
                  Icon(Icons.timer_outlined, size: 12, color: AppColors.textTertiary),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      'Eval Duration: ${cand.evaluationDurationMs}ms',
                      style: const TextStyle(color: AppColors.textTertiary, fontSize: 10),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        'Generated at ${_formatAbsoluteTime(cand.generatedAt)}',
                        style: const TextStyle(
                          color: AppColors.textTertiary,
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      Text(
                        _formatRelativeTime(cand.generatedAt),
                        style: const TextStyle(
                          color: AppColors.textTertiary,
                          fontSize: 9,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBreakdownChip(String category, int score, int maxScore) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        '$category: $score/$maxScore',
        style: const TextStyle(
          color: AppColors.textSecondary,
          fontSize: 9,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildPriceItem(String label, String value, Color valueColor) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(color: AppColors.textTertiary, fontSize: 10),
          ),
          const SizedBox(height: 2),
          Text(
            value,
            style: TextStyle(
              color: valueColor,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSnapshotItem(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 9, color: AppColors.textTertiary),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: const TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
          overflow: TextOverflow.ellipsis,
        ),
      ],
    );
  }
}
