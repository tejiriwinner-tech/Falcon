import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../models/signal.dart';
import '../../services/api/api_service.dart';
import '../../widgets/cards/signal_card.dart';
import '../../widgets/typography/section_title.dart';

class SignalsScreen extends StatefulWidget {
  const SignalsScreen({super.key});

  @override
  State<SignalsScreen> createState() => _SignalsScreenState();
}

class _SignalsScreenState extends State<SignalsScreen> {
  late Future<SignalListResponse> _signalsFuture;
  final ApiService _apiService = ApiService();
  final ScrollController _scrollController = ScrollController();
  bool _isLoadingMore = false;
  List<Signal> _allSignals = [];

  @override
  void initState() {
    super.initState();
    _fetchSignals();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >= _scrollController.position.maxScrollExtent - 200 && !_isLoadingMore) {
      _loadMoreSignals();
    }
  }

  void _fetchSignals() {
    setState(() {
      _allSignals = [];
      _signalsFuture = _apiService.getSignals();
    });
  }

  Future<void> _loadMoreSignals() async {
    if (_isLoadingMore) return;
    setState(() {
      _isLoadingMore = true;
    });

    try {
      final newSignals = await _apiService.getSignals();
      setState(() {
        _allSignals.addAll(newSignals.signals);
        _isLoadingMore = false;
      });
    } catch (e) {
      setState(() {
        _isLoadingMore = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Live Signals'),
        actions: [
          Container(
            margin: const EdgeInsets.only(right: 16),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: AppColors.success.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: AppColors.success.withValues(alpha: 0.4)),
            ),
            child: Row(
              children: [
                Container(
                  width: 7,
                  height: 7,
                  decoration: const BoxDecoration(
                    color: AppColors.success,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 6),
                const Text(
                  'LIVE',
                  style: TextStyle(
                    color: AppColors.success,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1.2,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
      body: FutureBuilder<SignalListResponse>(
        future: _signalsFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          } else if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24.0),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.error_outline, size: 64, color: AppColors.error),
                    const SizedBox(height: 16),
                    const Text(
                      'Failed to load signals',
                      style: TextStyle(color: AppColors.textPrimary, fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      snapshot.error.toString().replaceAll('Exception: ', ''),
                      style: const TextStyle(color: AppColors.textSecondary, fontSize: 14),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 24),
                    ElevatedButton(
                      onPressed: _fetchSignals,
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              ),
            );
          } else if (snapshot.hasData) {
            final allSignals = snapshot.data!.signals;
            _allSignals = allSignals; // Store for pagination
            
            if (allSignals.isEmpty) {
              return const Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.signal_wifi_off, size: 64, color: AppColors.textTertiary),
                    SizedBox(height: 16),
                    Text(
                      'No signals right now.',
                      style: TextStyle(color: AppColors.textSecondary, fontSize: 16),
                    ),
                    SizedBox(height: 8),
                    Text(
                      'Check back during active market sessions.',
                      style: TextStyle(color: AppColors.textTertiary, fontSize: 13),
                    ),
                  ],
                ),
              );
            }
            
            final activeSignals = allSignals.where((s) => s.status == 'ACTIVE').toList();
            final pendingSignals = allSignals.where((s) => s.status != 'ACTIVE').toList();
            final displaySignals = [...activeSignals, ...pendingSignals];
            
            final titleText = activeSignals.isNotEmpty
                ? 'Curated Live Setups (${activeSignals.length} Active)'
                : 'Curated Watchlist (0 Cleared)';
            final subtitleText = activeSignals.isNotEmpty
                ? '${activeSignals.length} trade${activeSignals.length != 1 ? 's' : ''} approved for execution • Max 3 top setups'
                : 'Capital Defense active • Setups awaiting entry trigger';
            
            return Column(
              children: [
                SectionTitle(
                  title: titleText,
                  subtitle: subtitleText,
                ),
                if (activeSignals.isEmpty) _buildCapitalDefenseBanner(),
                Expanded(
                  child: ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(16),
                    itemCount: displaySignals.length + (_isLoadingMore ? 1 : 0),
                    itemBuilder: (context, index) {
                      if (index == displaySignals.length) {
                        return const Center(
                          child: Padding(
                            padding: EdgeInsets.all(16),
                            child: CircularProgressIndicator(),
                          ),
                        );
                      }
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: SignalCard(signal: displaySignals[index]),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 8),
                _buildDisclaimer(),
              ],
            );
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }

  Widget _buildCapitalDefenseBanner() {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.warning.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.warning.withValues(alpha: 0.35)),
      ),
      child: const Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.shield_outlined, color: AppColors.warning, size: 20),
          SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'CAPITAL DEFENSE ACTIVE: 0 TRADES CLEARED',
                  style: TextStyle(
                    color: AppColors.warning,
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                SizedBox(height: 4),
                Text(
                  'Current market session / spread conditions do not offer a high-probability edge. Setups below are on WATCHLIST with strict entry triggers. DO NOT execute on MT5 until confirmed ACTIVE.',
                  style: TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 11,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDisclaimer() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.surfaceLight.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.textTertiary.withValues(alpha: 0.3)),
      ),
      child: const Text(
        '⚠️  Signals are AI-generated. Always apply proper risk management. Past performance does not guarantee future results.',
        style: TextStyle(
          color: AppColors.textTertiary,
          fontSize: 11,
          height: 1.5,
        ),
        textAlign: TextAlign.center,
      ),
    );
  }
}
