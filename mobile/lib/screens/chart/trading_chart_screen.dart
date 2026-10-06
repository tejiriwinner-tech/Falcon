import 'dart:async';
import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../models/candle_data.dart';
import '../../services/api/api_service.dart';
import '../../widgets/chart/interactive_trading_chart.dart';

class TradingChartScreen extends StatefulWidget {
  final String symbol;
  final String initialTimeframe;
  final TradeCorridorOverlay? tradeOverlay;
  final String? strategyName;
  final int? convictionScore;

  const TradingChartScreen({
    super.key,
    required this.symbol,
    this.initialTimeframe = '15m',
    this.tradeOverlay,
    this.strategyName,
    this.convictionScore,
  });

  @override
  State<TradingChartScreen> createState() => _TradingChartScreenState();
}

class _TradingChartScreenState extends State<TradingChartScreen> {
  final ApiService _apiService = ApiService();
  late String _activeTimeframe;
  List<CandleData> _candles = [];
  SMCStructureData? _smcStructure;
  bool _isLoading = true;
  String? _errorMessage;
  Timer? _liveRefreshTimer;

  @override
  void initState() {
    super.initState();
    _activeTimeframe = widget.initialTimeframe;
    _loadChartData();
    // Live tick / candle poll every 15 seconds
    _liveRefreshTimer = Timer.periodic(const Duration(seconds: 15), (_) {
      if (mounted) _pollLatestCandle();
    });
  }

  @override
  void dispose() {
    _liveRefreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadChartData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final candlesFuture = _apiService.getCandles(
        symbol: widget.symbol,
        timeframe: _activeTimeframe,
        limit: 120,
      );

      final smcFuture = _apiService.getSMCStructure(
        symbol: widget.symbol,
        timeframe: _activeTimeframe,
      );

      final results = await Future.wait([candlesFuture, smcFuture]);

      if (mounted) {
        setState(() {
          _candles = results[0] as List<CandleData>;
          _smcStructure = results[1] as SMCStructureData;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString().replaceAll('Exception: ', '');
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _pollLatestCandle() async {
    try {
      final freshBars = await _apiService.getCandles(
        symbol: widget.symbol,
        timeframe: _activeTimeframe,
        limit: 15,
      );
      if (freshBars.isNotEmpty && mounted) {
        setState(() {
          // Merge latest candles into existing list
          final Map<DateTime, CandleData> map = {for (var c in _candles) c.barTime: c};
          for (var fresh in freshBars) {
            map[fresh.barTime] = fresh;
          }
          _candles = map.values.toList()..sort((a, b) => a.barTime.compareTo(b.barTime));
        });
      }
    } catch (_) {}
  }

  void _onTimeframeChanged(String tf) {
    if (_activeTimeframe.toLowerCase() == tf.toLowerCase()) return;
    setState(() {
      _activeTimeframe = tf;
    });
    _loadChartData();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final isJpy = widget.symbol.contains('JPY');
    final double? latestPrice = _candles.isNotEmpty ? _candles.last.close : null;
    final String priceStr = latestPrice != null
        ? latestPrice.toStringAsFixed(isJpy ? 3 : 5)
        : '---';

    return Scaffold(
      backgroundColor: isDark ? const Color(0xFF0D1117) : const Color(0xFFF9FAFB),
      appBar: AppBar(
        title: Row(
          children: [
            Text(
              widget.symbol,
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: AppColors.primary.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                _activeTimeframe.toUpperCase(),
                style: const TextStyle(
                  color: AppColors.primary,
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            const Spacer(),
            // Current Price
            Text(
              priceStr,
              style: TextStyle(
                color: _candles.isNotEmpty && _candles.last.isBullish
                    ? AppColors.success
                    : AppColors.error,
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            tooltip: 'Refresh Candlesticks',
            onPressed: _loadChartData,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Conviction & Strategy Banner if opened from a Signal
            if (widget.convictionScore != null || widget.tradeOverlay != null)
              _buildSetupHeader(isDark),

            // Chart Body
            Expanded(
              child: _isLoading
                  ? const Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          CircularProgressIndicator(strokeWidth: 2.5),
                          SizedBox(height: 12),
                          Text(
                            'Loading Institutional Liquidity & SMC Data...',
                            style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
                          ),
                        ],
                      ),
                    )
                  : _errorMessage != null
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(24.0),
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const Icon(Icons.error_outline_rounded,
                                    color: AppColors.error, size: 48),
                                const SizedBox(height: 12),
                                Text(
                                  'Error Loading Market Chart',
                                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                        fontWeight: FontWeight.bold,
                                      ),
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  _errorMessage!,
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
                                ),
                                const SizedBox(height: 16),
                                ElevatedButton.icon(
                                  onPressed: _loadChartData,
                                  icon: const Icon(Icons.refresh, size: 16),
                                  label: const Text('Try Again'),
                                ),
                              ],
                            ),
                          ),
                        )
                      : InteractiveTradingChart(
                          candles: _candles,
                          smcStructure: _smcStructure,
                          tradeOverlay: widget.tradeOverlay,
                          activeTimeframe: _activeTimeframe,
                          onTimeframeChanged: _onTimeframeChanged,
                          onRefresh: _loadChartData,
                        ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSetupHeader(bool isDark) {
    final overlay = widget.tradeOverlay;
    final isBuy = overlay?.isBuy ?? true;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF161B22) : Colors.white,
        border: Border(
          bottom: BorderSide(
            color: (isDark ? Colors.white : Colors.black).withValues(alpha: 0.08),
          ),
        ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              if (overlay != null)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: (isBuy ? AppColors.success : AppColors.error).withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    isBuy ? '🟢 LIVE BUY' : '🔴 LIVE SELL',
                    style: TextStyle(
                      color: isBuy ? AppColors.success : AppColors.error,
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              if (widget.strategyName != null) ...[
                const SizedBox(width: 8),
                Text(
                  widget.strategyName!,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppColors.textPrimary,
                  ),
                ),
              ],
            ],
          ),
          if (widget.convictionScore != null)
            Row(
              children: [
                const Icon(Icons.verified_rounded, size: 14, color: AppColors.primary),
                const SizedBox(width: 4),
                Text(
                  'Conviction: ${widget.convictionScore}%',
                  style: const TextStyle(
                    color: AppColors.primary,
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
        ],
      ),
    );
  }
}
