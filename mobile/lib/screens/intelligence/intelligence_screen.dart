import 'package:flutter/material.dart';
import '../../services/api/api_service.dart';
import '../../models/intelligence.dart';
import '../../core/constants/app_colors.dart';

/// Falcon Intelligence Screen
/// 
/// Displays comprehensive AI trading intelligence including:
/// - Overall Decision (BUY/SELL/WAIT/AVOID)
/// - AI Confidence
/// - Signal Score
/// - Risk Score
/// - Confluence Score
/// - Market State
/// - Trend
/// - Entry Quality
/// - Risk Management Levels
/// - Reasoning
class IntelligenceScreen extends StatefulWidget {
  const IntelligenceScreen({super.key});

  @override
  State<IntelligenceScreen> createState() => _IntelligenceScreenState();
}

class _IntelligenceScreenState extends State<IntelligenceScreen> {
  String _selectedSymbol = 'XAUUSD';
  String _selectedTimeframe = 'H1';
  bool _isLoading = false;
  IntelligenceData? _intelligenceData;
  String? _errorMessage;
  final ApiService _apiService = ApiService();

  final List<String> _symbols = ['XAUUSD', 'GBPUSD', 'EURUSD', 'USDJPY'];
  final List<String> _timeframes = ['M5', 'M15', 'M30', 'H1', 'H4', 'D1'];

  @override
  void initState() {
    super.initState();
    _loadIntelligence();
  }

  Future<void> _loadIntelligence() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final response = await _apiService.getIntelligence(_selectedSymbol, _selectedTimeframe);
      setState(() {
        _intelligenceData = response.data;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = 'Error: $e';
        _isLoading = false;
      });
    }
  }

  Color _getDecisionColor(String decision) {
    switch (decision) {
      case 'BUY':
        return AppColors.success;
      case 'SELL':
        return AppColors.error;
      case 'WAIT':
        return AppColors.warning;
      case 'AVOID':
        return AppColors.textSecondary;
      default:
        return AppColors.textSecondary;
    }
  }

  Color _getScoreColor(double score) {
    if (score >= 80) return AppColors.success;
    if (score >= 60) return AppColors.warning;
    return AppColors.error;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Intelligence'),
      ),
      body: Column(
        children: [
          // Instrument & Timeframe Selector
          _buildControlPanel(),
          
          // Intelligence Display
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _errorMessage != null
                    ? Center(
                        child: Text(
                          _errorMessage!,
                          style: const TextStyle(color: AppColors.error),
                        ),
                      )
                    : _intelligenceData != null
                        ? _buildIntelligenceDisplay()
                        : const Center(
                            child: Text(
                              'No data available',
                              style: TextStyle(color: AppColors.textSecondary),
                            ),
                          ),
          ),
        ],
      ),
    );
  }

  Widget _buildControlPanel() {
    return Container(
      padding: const EdgeInsets.all(16.0),
      color: AppColors.surface,
      child: Row(
        children: [
          // Symbol Selector
          Expanded(
            child: DropdownButton<String>(
              value: _selectedSymbol,
              isExpanded: true,
              dropdownColor: AppColors.surface,
              style: const TextStyle(color: AppColors.textPrimary),
              items: _symbols.map((symbol) {
                return DropdownMenuItem(
                  value: symbol,
                  child: Text(symbol),
                );
              }).toList(),
              onChanged: (value) {
                if (value != null) {
                  setState(() {
                    _selectedSymbol = value;
                  });
                  _loadIntelligence();
                }
              },
            ),
          ),
          const SizedBox(width: 16),
          // Timeframe Selector
          Expanded(
            child: DropdownButton<String>(
              value: _selectedTimeframe,
              isExpanded: true,
              dropdownColor: AppColors.surface,
              style: const TextStyle(color: AppColors.textPrimary),
              items: _timeframes.map((tf) {
                return DropdownMenuItem(
                  value: tf,
                  child: Text(tf),
                );
              }).toList(),
              onChanged: (value) {
                if (value != null) {
                  setState(() {
                    _selectedTimeframe = value;
                  });
                  _loadIntelligence();
                }
              },
            ),
          ),
          const SizedBox(width: 16),
          // Refresh Button
          IconButton(
            icon: const Icon(Icons.refresh, color: AppColors.textPrimary),
            onPressed: _loadIntelligence,
          ),
        ],
      ),
    );
  }

  Widget _buildIntelligenceDisplay() {
    final data = _intelligenceData!;
    final decision = data.decision;
    final confidence = data.confidence;
    final signalScore = data.signalScore;
    final riskScore = data.riskScore;
    final confluenceScore = data.confluenceScore;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Overall Decision Card
          _buildDecisionCard(decision, confidence),
          const SizedBox(height: 16),

          // Scores Row
          Row(
            children: [
              Expanded(
                child: _buildScoreCard(
                  'Signal Score',
                  signalScore,
                  Icons.signal_cellular_alt,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: _buildScoreCard(
                  'Confidence',
                  confidence,
                  Icons.psychology,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          Row(
            children: [
              Expanded(
                child: _buildScoreCard(
                  'Confluence',
                  confluenceScore,
                  Icons.merge_type,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: _buildScoreCard(
                  'Risk Score',
                  riskScore,
                  Icons.warning,
                  inverse: true,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Market State & Trend
          _buildInfoCard(
            'Market State',
            data.marketState,
            Icons.analytics,
          ),
          const SizedBox(height: 16),

          _buildInfoCard(
            'Trend',
            data.trend,
            Icons.trending_up,
          ),
          const SizedBox(height: 16),

          _buildInfoCard(
            'Entry Quality',
            data.entry ?? 'N/A',
            Icons.place,
          ),
          const SizedBox(height: 16),

          // Risk Management Levels
          _buildRiskManagementCard(data),
          const SizedBox(height: 16),

          // Reasoning Card
          _buildReasoningCard(data.reasoning ?? 'No reasoning available'),
        ],
      ),
    );
  }

  Widget _buildDecisionCard(String decision, double confidence) {
    final color = _getDecisionColor(decision);

    return Card(
      color: AppColors.surface,
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          children: [
            const Text(
              'AI DECISION',
              style: TextStyle(
                color: AppColors.textSecondary,
                fontSize: 14,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: color, width: 2),
              ),
              child: Text(
                decision,
                style: TextStyle(
                  color: color,
                  fontSize: 32,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              '${confidence.toStringAsFixed(1)}% Confidence',
              style: const TextStyle(
                color: AppColors.textSecondary,
                fontSize: 16,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildScoreCard(
    String label,
    double score,
    IconData icon, {
    bool inverse = false,
  }) {
    final displayScore = inverse ? 100 - score : score;
    final color = _getScoreColor(displayScore);

    return Card(
      color: AppColors.surface,
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            Icon(icon, color: color, size: 32),
            const SizedBox(height: 8),
            Text(
              label,
              style: const TextStyle(
                color: AppColors.textSecondary,
                fontSize: 12,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              score.toStringAsFixed(1),
              style: TextStyle(
                color: color,
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoCard(String label, String value, IconData icon) {
    return Card(
      color: AppColors.surface,
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ListTile(
        leading: Icon(icon, color: AppColors.primary, size: 32),
        title: Text(
          label,
          style: const TextStyle(
            color: AppColors.textSecondary,
            fontSize: 14,
          ),
        ),
        subtitle: Text(
          value,
          style: const TextStyle(
            color: AppColors.textPrimary,
            fontSize: 18,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }

  Widget _buildRiskManagementCard(IntelligenceData data) {
    final entry = data.entry;
    final stop = data.stop;
    final target = data.target;

    return Card(
      color: AppColors.surface,
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.shield, color: AppColors.primary, size: 24),
                SizedBox(width: 8),
                Text(
                  'Risk Management',
                  style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const Divider(color: AppColors.textTertiary),
            const SizedBox(height: 8),
            if (entry != null) _buildLevelRow('Entry', double.tryParse(entry) ?? 0.0, AppColors.primary),
            if (stop != null) _buildLevelRow('Stop Loss', stop, AppColors.error),
            if (target != null) _buildLevelRow('Target', target, AppColors.success),
          ],
        ),
      ),
    );
  }

  Widget _buildLevelRow(String label, double value, Color color,
      {bool isRatio = false}) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: AppColors.textSecondary,
            fontSize: 14,
          ),
        ),
        Text(
          isRatio ? value.toStringAsFixed(2) : value.toStringAsFixed(2),
          style: TextStyle(
            color: color,
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }

  Widget _buildReasoningCard(String reasoning) {
    return Card(
      color: AppColors.surface,
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.lightbulb, color: AppColors.warning, size: 24),
                SizedBox(width: 8),
                Text(
                  'AI Reasoning',
                  style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const Divider(color: AppColors.textTertiary),
            const SizedBox(height: 8),
            Text(
              reasoning,
              style: const TextStyle(
                color: AppColors.textSecondary,
                fontSize: 14,
                height: 1.5,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
