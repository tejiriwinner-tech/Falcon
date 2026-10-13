import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../models/signal.dart';
import '../../services/api/api_service.dart';
import '../../services/signals/signal_pin_service.dart';
import '../../widgets/cards/signal_card.dart';
import '../../widgets/typography/section_title.dart';

enum SignalFilter { all, pinned, active, watchlist, resolved }

class SignalsScreen extends StatefulWidget {
  const SignalsScreen({super.key});

  @override
  State<SignalsScreen> createState() => _SignalsScreenState();
}

class _SignalsScreenState extends State<SignalsScreen> {
  late Future<SignalListResponse> _signalsFuture;
  final ApiService _apiService = ApiService();
  final SignalPinService _pinService = SignalPinService();
  final ScrollController _scrollController = ScrollController();
  SignalFilter _selectedFilter = SignalFilter.all;

  @override
  void initState() {
    super.initState();
    _pinService.init();
    _pinService.addListener(_onPinServiceChanged);
    _signalsFuture = _apiService.getSignals();
  }

  @override
  void dispose() {
    _pinService.removeListener(_onPinServiceChanged);
    _scrollController.dispose();
    super.dispose();
  }

  void _onPinServiceChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  Future<void> _refreshSignals() async {
    setState(() {
      _signalsFuture = _apiService.getSignals();
    });
    await _signalsFuture;
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
                      onPressed: _refreshSignals,
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              ),
            );
          } else if (snapshot.hasData) {
            final rawSignals = snapshot.data!.signals;
            _pinService.updateWithLiveSignals(rawSignals);

            // Strict deduplication by uniqueKey (symbol + action + entry + stopLoss)
            final seenKeys = <String>{};
            final deduplicatedList = <Signal>[];

            for (final s in rawSignals) {
              if (seenKeys.add(s.uniqueKey)) {
                final isPinned = _pinService.isPinned(s);
                deduplicatedList.add(s.copyWith(isPinned: isPinned));
              }
            }

            // Also include any locally pinned setups if not already present in the active feed
            for (final ps in _pinService.pinnedSignals) {
              if (seenKeys.add(ps.uniqueKey)) {
                deduplicatedList.add(ps.copyWith(isPinned: true));
              }
            }

            if (deduplicatedList.isEmpty) {
              return RefreshIndicator(
                onRefresh: _refreshSignals,
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  children: const [
                    SizedBox(height: 120),
                    Center(
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
                            'Pull down to refresh or check during active market hours.',
                            style: TextStyle(color: AppColors.textTertiary, fontSize: 13),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              );
            }

            final pinnedSignals = deduplicatedList.where((s) => _pinService.isPinned(s) || s.isPinned).toList();
            final activeSignals = deduplicatedList.where((s) => s.status.toUpperCase() == 'ACTIVE' || s.status.toUpperCase() == 'OPEN').toList();
            final watchlistSignals = deduplicatedList.where((s) => s.status.toUpperCase() == 'HOLD' || s.status.toUpperCase() == 'WAITING' || s.status.toUpperCase() == 'PENDING').toList();
            final resolvedSignals = deduplicatedList.where((s) => ['WON', 'WIN', 'LOST', 'LOSS', 'BREAKEVEN', 'BE', 'CLOSED', 'EXPIRED'].contains(s.status.toUpperCase())).toList();

            return RefreshIndicator(
              onRefresh: _refreshSignals,
              child: Column(
                children: [
                  // Filter selection bar
                  _buildFilterChips(
                    allCount: deduplicatedList.length,
                    pinnedCount: pinnedSignals.length,
                    activeCount: activeSignals.length,
                    watchlistCount: watchlistSignals.length,
                    resolvedCount: resolvedSignals.length,
                  ),

                  // Header section info
                  _buildHeaderInfo(activeSignals.length),

                  // Signal List
                  Expanded(
                    child: _buildFilteredSignalList(
                      allSignals: deduplicatedList,
                      pinnedSignals: pinnedSignals,
                      activeSignals: activeSignals,
                      watchlistSignals: watchlistSignals,
                      resolvedSignals: resolvedSignals,
                    ),
                  ),

                  _buildDisclaimer(),
                ],
              ),
            );
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }

  Widget _buildFilterChips({
    required int allCount,
    required int pinnedCount,
    required int activeCount,
    required int watchlistCount,
    required int resolvedCount,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.surface.withValues(alpha: 0.6),
        border: Border(
          bottom: BorderSide(color: AppColors.textTertiary.withValues(alpha: 0.15)),
        ),
      ),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            _buildFilterChip('All', allCount, SignalFilter.all, Icons.dashboard_outlined),
            const SizedBox(width: 8),
            _buildFilterChip('Pinned', pinnedCount, SignalFilter.pinned, Icons.push_pin_outlined, badgeColor: AppColors.primary),
            const SizedBox(width: 8),
            _buildFilterChip('Active', activeCount, SignalFilter.active, Icons.bolt, badgeColor: AppColors.success),
            const SizedBox(width: 8),
            _buildFilterChip('Watchlist', watchlistCount, SignalFilter.watchlist, Icons.remove_red_eye_outlined, badgeColor: AppColors.warning),
            const SizedBox(width: 8),
            _buildFilterChip('Resolved', resolvedCount, SignalFilter.resolved, Icons.military_tech_outlined, badgeColor: AppColors.info),
          ],
        ),
      ),
    );
  }

  Widget _buildFilterChip(String label, int count, SignalFilter filter, IconData icon, {Color? badgeColor}) {
    final isSelected = _selectedFilter == filter;
    final chipColor = badgeColor ?? AppColors.primary;

    return InkWell(
      borderRadius: BorderRadius.circular(20),
      onTap: () {
        setState(() {
          _selectedFilter = filter;
        });
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? chipColor.withValues(alpha: 0.2) : AppColors.surfaceLight.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected ? chipColor : AppColors.textTertiary.withValues(alpha: 0.2),
            width: isSelected ? 1.5 : 1.0,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 14,
              color: isSelected ? chipColor : AppColors.textSecondary,
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                color: isSelected ? AppColors.textPrimary : AppColors.textSecondary,
                fontSize: 12,
                fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
              ),
            ),
            if (count > 0) ...[
              const SizedBox(width: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: isSelected ? chipColor : AppColors.surface,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  count.toString(),
                  style: TextStyle(
                    color: isSelected ? Colors.white : AppColors.textSecondary,
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildHeaderInfo(int activeCount) {
    final titleText = activeCount > 0
        ? 'Curated Live Setups ($activeCount Active)'
        : 'Watchlist Setups';
    final subtitleText = activeCount > 0
        ? '$activeCount trade${activeCount != 1 ? 's' : ''} approved for execution • Real-time validation'
        : 'Monitoring price action • Setups awaiting entry trigger';

    return Padding(
      padding: const EdgeInsets.only(top: 8.0),
      child: SectionTitle(
        title: titleText,
        subtitle: subtitleText,
      ),
    );
  }

  Widget _buildFilteredSignalList({
    required List<Signal> allSignals,
    required List<Signal> pinnedSignals,
    required List<Signal> activeSignals,
    required List<Signal> watchlistSignals,
    required List<Signal> resolvedSignals,
  }) {
    switch (_selectedFilter) {
      case SignalFilter.pinned:
        if (pinnedSignals.isEmpty) {
          return _buildEmptyState(
            icon: Icons.push_pin_outlined,
            title: 'No Pinned Setups',
            subtitle: 'Tap the 📌 pin button on any setup card to track whether it hits Target (Won), Stop Loss (Lost), or Breakeven.',
          );
        }
        return ListView(
          controller: _scrollController,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 4),
              child: Row(
                children: [
                  const Icon(Icons.push_pin, size: 16, color: AppColors.primary),
                  const SizedBox(width: 8),
                  Text(
                    '${pinnedSignals.length} Pinned Setup${pinnedSignals.length > 1 ? 's' : ''}',
                    style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold, fontSize: 13),
                  ),
                  const Spacer(),
                  InkWell(
                    borderRadius: BorderRadius.circular(6),
                    onTap: () async {
                      final confirm = await showDialog<bool>(
                        context: context,
                        builder: (ctx) => AlertDialog(
                          title: const Text('Clear All Pinned Setups?'),
                          content: const Text('This will unpin all setups from your tracking list.'),
                          actions: [
                            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
                            TextButton(
                              onPressed: () => Navigator.pop(ctx, true),
                              child: const Text('Clear All', style: TextStyle(color: AppColors.error)),
                            ),
                          ],
                        ),
                      );
                      if (confirm == true) {
                        await _pinService.clearAll();
                        if (mounted) setState(() {});
                      }
                    },
                    child: const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      child: Row(
                        children: [
                          Icon(Icons.clear_all, size: 16, color: AppColors.textTertiary),
                          SizedBox(width: 4),
                          Text('Clear All', style: TextStyle(color: AppColors.textTertiary, fontSize: 12)),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
            ...pinnedSignals.map((s) => _buildCardWrapper(s)),
          ],
        );

      case SignalFilter.active:
        if (activeSignals.isEmpty) {
          return _buildEmptyState(
            icon: Icons.bolt,
            title: 'No Active Trades',
            subtitle: 'Falcon is preserving capital. Trades will be cleared once entry conditions are confirmed.',
          );
        }
        return _buildSignalsListView(activeSignals);

      case SignalFilter.watchlist:
        if (watchlistSignals.isEmpty) {
          return _buildEmptyState(
            icon: Icons.remove_red_eye_outlined,
            title: 'Watchlist Empty',
            subtitle: 'No setups currently on the watchlist radar.',
          );
        }
        return _buildSignalsListView(watchlistSignals);

      case SignalFilter.resolved:
        if (resolvedSignals.isEmpty) {
          return _buildEmptyState(
            icon: Icons.military_tech_outlined,
            title: 'No Completed Trades Yet',
            subtitle: 'When active setups hit Take Profit (Won), Stop Loss (Lost), or Breakeven, their audited outcomes will appear here.',
          );
        }
        return _buildSignalsListView(resolvedSignals);

      case SignalFilter.all:
        // Structured arrange view:
        // 1. Pinned Setups (live tracking with status badge)
        // 2. Active Setups (current valid trades)
        // 3. Watchlist Setups (awaiting entry trigger)
        // 4. Completed Outcomes (WON / LOST / BREAKEVEN)
        final unpinnedActive = activeSignals.where((s) => !pinnedSignals.contains(s)).toList();
        final unpinnedWatchlist = watchlistSignals.where((s) => !pinnedSignals.contains(s)).toList();
        final unpinnedResolved = resolvedSignals.where((s) => !pinnedSignals.contains(s)).toList();

        return ListView(
          controller: _scrollController,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          children: [
            if (pinnedSignals.isNotEmpty) ...[
              _buildSectionSubHeader('📌 PINNED TRADES (LIVE TRACKING)', pinnedSignals.length, AppColors.primary),
              ...pinnedSignals.map((s) => _buildCardWrapper(s)),
              const SizedBox(height: 12),
            ],
            if (unpinnedActive.isNotEmpty) ...[
              _buildSectionSubHeader('⚡ ACTIVE TRADES (READY NOW)', unpinnedActive.length, AppColors.success),
              ...unpinnedActive.map((s) => _buildCardWrapper(s)),
              const SizedBox(height: 12),
            ],
            if (unpinnedWatchlist.isNotEmpty) ...[
              _buildSectionSubHeader('🎯 WATCHLIST SETUPS (WAITING FOR TRIGGER)', unpinnedWatchlist.length, AppColors.warning),
              ...unpinnedWatchlist.map((s) => _buildCardWrapper(s)),
              const SizedBox(height: 12),
            ],
            if (unpinnedResolved.isNotEmpty) ...[
              _buildSectionSubHeader('🏁 COMPLETED OUTCOMES (WON / LOST / BE)', unpinnedResolved.length, AppColors.info),
              ...unpinnedResolved.map((s) => _buildCardWrapper(s)),
              const SizedBox(height: 12),
            ],
          ],
        );
    }
  }

  Widget _buildSignalsListView(List<Signal> signals) {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.all(16),
      itemCount: signals.length,
      itemBuilder: (context, index) {
        return _buildCardWrapper(signals[index]);
      },
    );
  }

  Widget _buildCardWrapper(Signal signal) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: SignalCard(
        signal: signal,
        onPinChanged: () {
          setState(() {});
        },
      ),
    );
  }

  Widget _buildSectionSubHeader(String title, int count, Color color) {
    return Padding(
      padding: const EdgeInsets.only(top: 6, bottom: 10),
      child: Row(
        children: [
          Container(
            width: 3,
            height: 14,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 8),
          Text(
            title,
            style: TextStyle(
              color: color,
              fontSize: 12,
              fontWeight: FontWeight.bold,
              letterSpacing: 0.8,
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Text(
              count.toString(),
              style: TextStyle(
                color: color,
                fontSize: 10,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState({
    required IconData icon,
    required String title,
    required String subtitle,
  }) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 56, color: AppColors.textTertiary),
            const SizedBox(height: 16),
            Text(
              title,
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              subtitle,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: AppColors.textSecondary,
                fontSize: 13,
                height: 1.4,
              ),
            ),
          ],
        ),
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
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 12),
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
