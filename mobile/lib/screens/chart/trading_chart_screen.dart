import 'dart:math' as math;
import 'dart:async';
import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../core/utils/price_formatter.dart';
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
  SessionBreakoutStructureData? _sessionStructure;
  bool _isLoading = true;
  String? _errorMessage;
  Timer? _liveRefreshTimer;
  Timer? _liveQuoteTimer;
  double? _livePrice;

  static String _normalizeTimeframe(String tf) {
    final clean = tf.trim().toLowerCase();
    switch (clean) {
      case 'm5':
      case '5m':
        return '5m';
      case 'm15':
      case '15m':
        return '15m';
      case 'm30':
      case '30m':
        return '30m';
      case 'h1':
      case '1h':
        return '1h';
      case 'h4':
      case '4h':
        return '4h';
      case 'd1':
      case '1d':
        return '1d';
      default:
        return clean.isEmpty ? '15m' : clean;
    }
  }

  @override
  void initState() {
    super.initState();
    _activeTimeframe = _normalizeTimeframe(widget.initialTimeframe);
    _loadChartData();
    // Fast live tick poll (every 3 seconds) for real-time candle breathing & pulsing marker
    _liveQuoteTimer = Timer.periodic(const Duration(seconds: 3), (_) {
      if (mounted) _pollLiveQuote();
    });
    // History backfill poll (every 20 seconds)
    _liveRefreshTimer = Timer.periodic(const Duration(seconds: 20), (_) {
      if (mounted) _pollLatestCandle();
    });
  }

  @override
  void dispose() {
    _liveQuoteTimer?.cancel();
    _liveRefreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadChartData() async {
    final requestedTf = _activeTimeframe;
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final candlesFuture = _apiService.getCandles(
        symbol: widget.symbol,
        timeframe: requestedTf,
        limit: 120,
      );

      final sessionFuture = _apiService.getSessionBreakoutStructure(
        symbol: widget.symbol,
        timeframe: requestedTf,
      ).catchError((_) => SessionBreakoutStructureData.empty(widget.symbol, requestedTf));

      final results = await Future.wait([candlesFuture, sessionFuture]);

      if (mounted && _activeTimeframe == requestedTf) {
        setState(() {
          _candles = results[0] as List<CandleData>;
          _sessionStructure = results[1] as SessionBreakoutStructureData;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted && _activeTimeframe == requestedTf) {
        setState(() {
          _errorMessage = e.toString().replaceAll('Exception: ', '');
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _pollLatestCandle() async {
    final requestedTf = _activeTimeframe;
    try {
      final freshBars = await _apiService.getCandles(
        symbol: widget.symbol,
        timeframe: requestedTf,
        limit: 15,
      );
      if (freshBars.isNotEmpty && mounted && _activeTimeframe == requestedTf) {
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

  Future<void> _pollLiveQuote() async {
    try {
      final quoteResp = await _apiService.getMarketQuote(widget.symbol);
      final price = quoteResp.quote.lastPrice;
      if (price > 0 && mounted) {
        setState(() {
          _livePrice = price;
          _fuseLivePriceIntoActiveCandle(price, tickTime: quoteResp.quote.timestamp);
        });
      }
    } catch (_) {}
  }

  int _parseTimeframeMinutes(String tf) {
    final lower = _normalizeTimeframe(tf);
    if (lower.contains('5m')) return 5;
    if (lower.contains('15m')) return 15;
    if (lower.contains('30m')) return 30;
    if (lower.contains('1h')) return 60;
    if (lower.contains('4h')) return 240;
    if (lower.contains('1d')) return 1440;
    return 15;
  }

  DateTime _normalizeBarBucket(DateTime dt, int minutes) {
    final utc = dt.toUtc();
    final bucketMs = (utc.millisecondsSinceEpoch ~/ (minutes * 60000)) * minutes * 60000;
    return DateTime.fromMillisecondsSinceEpoch(bucketMs, isUtc: true);
  }

  void _fuseLivePriceIntoActiveCandle(double price, {DateTime? tickTime}) {
    if (_candles.isEmpty || price <= 0) return;

    final now = (tickTime ?? DateTime.now()).toUtc();
    final int tfMinutes = _parseTimeframeMinutes(_activeTimeframe);
    final currentBucket = _normalizeBarBucket(now, tfMinutes);
    final last = _candles.last;

    if (currentBucket.isAfter(last.barTime)) {
      // New candle interval has begun — instantiate new active candle
      _candles.add(CandleData(
        symbol: widget.symbol,
        timeframe: _activeTimeframe,
        barTime: currentBucket,
        open: last.close,
        high: math.max(last.close, price),
        low: math.min(last.close, price),
        close: price,
        volume: 100.0,
      ));
    } else {
      // Still inside current candle interval — expand wicks & breathe body live
      final updatedCandle = CandleData(
        symbol: widget.symbol,
        timeframe: _activeTimeframe,
        barTime: last.barTime,
        open: last.open,
        high: math.max(last.high, price),
        low: math.min(last.low, price),
        close: price,
        volume: (last.volume ?? 100.0) + 1.0,
      );
      _candles[_candles.length - 1] = updatedCandle;
    }
  }

  void _onTimeframeChanged(String tf) {
    final normTf = _normalizeTimeframe(tf);
    if (_activeTimeframe.toLowerCase() == normTf.toLowerCase()) return;
    setState(() {
      _activeTimeframe = normTf;
    });
    _loadChartData();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final double? latestPrice = _candles.isNotEmpty ? _candles.last.close : null;
    final String priceStr = latestPrice != null
        ? PriceFormatter.format(widget.symbol, latestPrice)
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
            // Weekend Standby Notice
            if (DateTime.now().toUtc().weekday == 6 ||
                (DateTime.now().toUtc().weekday == 7 && DateTime.now().toUtc().hour < 21))
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                color: const Color(0xFFF59E0B).withValues(alpha: 0.15),
                child: const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.lock_clock_rounded, size: 14, color: Color(0xFFF59E0B)),
                    SizedBox(width: 6),
                    Text(
                      'WEEKEND STANDBY • Live Analysis Active • Market Reopens Sun 21:00 UTC',
                      style: TextStyle(
                        color: Color(0xFFF59E0B),
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),

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
                            'Loading Session Corridors & Volatility Envelopes...',
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
                          sessionStructure: _sessionStructure,
                          tradeOverlay: widget.tradeOverlay,
                          activeTimeframe: _activeTimeframe,
                          livePrice: _livePrice,
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
