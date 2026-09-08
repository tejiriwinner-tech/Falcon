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
                ? '${activeSignals.length} Active Signal${activeSignals.length != 1 ? 's' : ''}'
                : '0 Active Signals';
            final subtitleText = activeSignals.isNotEmpty
                ? 'Approved for immediate execution'
                : (pendingSignals.isNotEmpty
                    ? '${pendingSignals.length} setup${pendingSignals.length != 1 ? 's' : ''} under review (pending)'
                    : 'Updated live during market hours');
            
            return Column(
              children: [
                SectionTitle(
                  title: titleText,
                  subtitle: subtitleText,
                ),
                const SizedBox(height: 16),
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
