import 'dart:async';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../services/api/api_service.dart';
import '../../models/market_quote.dart';
import '../../models/provider_models.dart' hide LegacyMarketQuote;
import '../../widgets/cards/app_card.dart';
import '../../widgets/typography/section_title.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';
import '../../core/utils/price_formatter.dart';

class MarketQuotesScreen extends StatefulWidget {
  const MarketQuotesScreen({super.key});

  @override
  State<MarketQuotesScreen> createState() => _MarketQuotesScreenState();
}

class _MarketQuotesScreenState extends State<MarketQuotesScreen> {
  final ApiService _apiService = ApiService();
  late Future<List<MarketQuote>> _watchlistFuture;
  late Future<ProviderListResponse> _providersFuture;
  List<MarketQuote>? _cachedQuotes;
  ProviderListResponse? _cachedProviders;
  Timer? _timer;
  DateTime _lastRefresh = DateTime.now();

  @override
  void initState() {
    super.initState();
    _fetchData();
    _timer = Timer.periodic(const Duration(seconds: 12), (timer) {
      if (mounted) {
        _fetchData();
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _fetchData() {
    setState(() {
      _watchlistFuture = _apiService.getWatchlist(
        symbols: ['XAUUSD', 'GBPUSD', 'EURUSD', 'GBPJPY', 'USDJPY', 'AUDUSD', 'NAS100', 'US30'],
      ).then((quotes) {
        if (mounted) {
          setState(() => _cachedQuotes = quotes);
        }
        return quotes;
      });
      _providersFuture = _apiService.getProviders().then((providers) {
        if (mounted) {
          setState(() => _cachedProviders = providers);
        }
        return providers;
      });
      _lastRefresh = DateTime.now();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchData();
    try {
      await Future.wait([_watchlistFuture, _providersFuture]);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Market Data Intelligence'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _handleRefresh,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _handleRefresh,
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16.0),
          physics: const AlwaysScrollableScrollPhysics(),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              FutureBuilder<List<MarketQuote>>(
                future: _watchlistFuture,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting && _cachedQuotes == null) {
                    return const PlaceholderCard(height: 120);
                  }
                  final quotes = snapshot.data ?? _cachedQuotes ?? [];
                  final avgFreshness = quotes.isNotEmpty
                      ? quotes.map((q) => q.freshnessSeconds).fold(0.0, (a, b) => a + b) / quotes.length
                      : 0.0;
                  final providerName = quotes.isNotEmpty ? quotes.first.providerName : 'Twelve Data';

                  return _buildSummaryCard(
                    providerName: providerName,
                    quotesLoaded: quotes.length,
                    avgFreshness: avgFreshness,
                  );
                },
              ),
              const SizedBox(height: 24),
              const SectionTitle(
                title: 'Primary Trading Instruments',
                subtitle: 'XAUUSD & GBPUSD first-class watchlist',
              ),
              const SizedBox(height: 16),
              FutureBuilder<List<MarketQuote>>(
                future: _watchlistFuture,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting && _cachedQuotes == null) {
                    return const PlaceholderCard(height: 300);
                  } else if (snapshot.hasError && _cachedQuotes == null) {
                    return AppCard(
                      child: Padding(
                        padding: const EdgeInsets.all(16.0),
                        child: Text(
                          'Error loading market quotes: ${snapshot.error}',
                          style: const TextStyle(color: AppColors.error),
                        ),
                      ),
                    );
                  } else if (snapshot.hasData || _cachedQuotes != null) {
                    final quotes = snapshot.data ?? _cachedQuotes!;
                    return ListView.separated(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: quotes.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 12),
                      itemBuilder: (context, index) {
                        return _buildQuoteCard(quotes[index]);
                      },
                    );
                  }
                  return const SizedBox.shrink();
                },
              ),
              const SizedBox(height: 24),
              const SectionTitle(
                title: 'Provider Health Panel',
                subtitle: 'Active failover & connection stats',
              ),
              const SizedBox(height: 16),
              FutureBuilder<ProviderListResponse>(
                future: _providersFuture,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting && _cachedProviders == null) {
                    return const PlaceholderCard(height: 160);
                  } else if (snapshot.hasData || _cachedProviders != null) {
                    return _buildProviderHealthPanel(snapshot.data ?? _cachedProviders!);
                  }
                  return const SizedBox.shrink();
                },
              ),
              const SizedBox(height: 24),
              _buildMetadataFooter(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSummaryCard({
    required String providerName,
    required int quotesLoaded,
    required double avgFreshness,
  }) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Active Gateway Provider',
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    providerName,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: AppColors.success.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.success.withValues(alpha: 0.3)),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.bolt, color: AppColors.success, size: 16),
                    SizedBox(width: 4),
                    Text(
                      'LIVE FEED',
                      style: TextStyle(
                        color: AppColors.success,
                        fontWeight: FontWeight.bold,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const Divider(height: 24, color: AppColors.surfaceLight),
          Row(
            children: [
              _buildSummaryStat('Quotes Loaded', '$quotesLoaded Instruments'),
              _buildSummaryStat('Last Refresh', DateFormat('HH:mm:ss').format(_lastRefresh)),
              _buildSummaryStat('Avg Freshness', '${avgFreshness.toStringAsFixed(1)}s'),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSummaryStat(String label, String value) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
          const SizedBox(height: 4),
          Text(
            value,
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
          ),
        ],
      ),
    );
  }

  Widget _buildQuoteCard(MarketQuote quote) {
    final isPos = quote.change >= 0;
    final changeSign = isPos ? '+' : '';

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Text(
                    quote.symbol,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  if (quote.symbol == 'XAUUSD' || quote.symbol == 'GBPUSD') ...[
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.primary.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: const Text(
                        'PRIMARY',
                        style: TextStyle(fontSize: 10, color: AppColors.primary, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: isPos ? AppColors.success.withValues(alpha: 0.1) : AppColors.error.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  '$changeSign${quote.changePercent.toStringAsFixed(2)}%',
                  style: TextStyle(
                    color: isPos ? AppColors.success : AppColors.error,
                    fontWeight: FontWeight.bold,
                    fontSize: 13,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                PriceFormatter.format(quote.symbol, quote.lastPrice),
                style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
              ),
              Text(
                'Spread: ${(quote.bidAsk.spread / PriceFormatter.pipSize(quote.symbol)).toStringAsFixed(1)}p',
                style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _buildPriceCell('Bid', PriceFormatter.format(quote.symbol, quote.bidAsk.bid)),
              _buildPriceCell('Ask', PriceFormatter.format(quote.symbol, quote.bidAsk.ask)),
              _buildPriceCell('Status', quote.quoteStatus.name),
              _buildPriceCell('Market', quote.marketStatus.name),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Provider: ${quote.providerName}',
                style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
              ),
              Text(
                'Freshness: ${quote.freshnessSeconds.toStringAsFixed(1)}s ago',
                style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPriceCell(String label, String value) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: AppColors.textSecondary, fontSize: 11)),
          const SizedBox(height: 2),
          Text(value, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
        ],
      ),
    );
  }

  Widget _buildProviderHealthPanel(ProviderListResponse data) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ...data.providers.map((p) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 8.0),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    p.metadata.providerName,
                    style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                  ),
                  Row(
                    children: [
                      Text(
                        '${p.latency.averageMs.toStringAsFixed(1)} ms',
                        style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                      ),
                      const SizedBox(width: 12),
                      Text(
                        p.metadata.status.name,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: p.metadata.status == ProviderStatus.ONLINE ? AppColors.success : AppColors.error,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildMetadataFooter() {
    return Center(
      child: Column(
        children: [
          const Text(
            'Falcon Market Data Gateway • v2.0',
            style: TextStyle(color: AppColors.textTertiary, fontSize: 12),
          ),
          const SizedBox(height: 4),
          Text(
            'Pipeline Stage: PROVIDER_FRAMEWORK',
            style: TextStyle(color: AppColors.textTertiary.withValues(alpha: 0.7), fontSize: 11),
          ),
        ],
      ),
    );
  }
}
