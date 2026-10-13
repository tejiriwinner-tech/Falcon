import 'package:flutter/material.dart';
import '../../services/api/api_service.dart';
import '../../models/copilot_models.dart';
import '../../models/candle_data.dart';
import '../../widgets/cards/app_card.dart';
import '../../core/constants/app_colors.dart';

class CopilotScreen extends StatefulWidget {
  const CopilotScreen({super.key});

  @override
  State<CopilotScreen> createState() => _CopilotScreenState();
}

class _ChatMessage {
  final bool isUser;
  final String text;
  final String? intent;
  final double? confidence;
  final Map<String, dynamic>? technicalContext;
  final Map<String, dynamic>? riskContext;
  final DateTime timestamp;

  _ChatMessage({
    required this.isUser,
    required this.text,
    this.intent,
    this.confidence,
    this.technicalContext,
    this.riskContext,
    required this.timestamp,
  });
}

class _CopilotScreenState extends State<CopilotScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabController;
  final ApiService _apiService = ApiService();
  final TextEditingController _queryController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  final List<_ChatMessage> _messages = [];
  bool _isQuerying = false;
  String _selectedSymbol = 'XAUUSD';

  // Briefing state
  IntelligenceBriefing? _currentBriefing;
  bool _isLoadingBriefing = false;
  String _selectedBriefingType = 'latest'; // 'latest', 'london-open', 'daily-review'
  bool _isDispatchingTelegram = false;
  String? _briefingError;

  // Session Breakout & Volatility state
  SessionBreakoutStructureData? _sessionData;
  bool _isLoadingSession = false;
  String _sessionSymbol = 'EURUSD';
  String? _sessionError;

  final List<String> _quickPrompts = [
    'Why did you trigger this Gold buy?',
    'What is our current streak and recovery headroom?',
    'What did you learn from the last loss?',
    'What is the active capital cycle?',
    'Explain the session breakout corridors for EURUSD',
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);

    // Initial Co-Pilot welcome message
    _messages.add(
      _ChatMessage(
        isUser: false,
        text: 'Greetings Trader. I am Falcon AI Co-Pilot—your institutional Session Momentum, Forensic Learning, and Capital Guardian intelligence.\n\nAsk me about trade rationales, current streak recovery progress, forensic lessons committed to memory, or session breakout corridors.',
        intent: 'GREETING',
        confidence: 1.0,
        timestamp: DateTime.now(),
      ),
    );

    _loadBriefing();
    _loadSessionStructure();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _queryController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _sendQuery(String queryText) async {
    final clean = queryText.trim();
    if (clean.isEmpty || _isQuerying) return;

    setState(() {
      _messages.add(_ChatMessage(
        isUser: true,
        text: clean,
        timestamp: DateTime.now(),
      ));
      _isQuerying = true;
    });

    _queryController.clear();
    _scrollToBottom();

    try {
      final response = await _apiService.queryCopilot(clean, symbol: _selectedSymbol);
      if (!mounted) return;
      setState(() {
        _messages.add(_ChatMessage(
          isUser: false,
          text: response.response,
          intent: response.intent,
          confidence: response.confidence,
          technicalContext: response.technicalContext,
          riskContext: response.riskContext,
          timestamp: DateTime.now(),
        ));
        _isQuerying = false;
      });
      _scrollToBottom();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _messages.add(_ChatMessage(
          isUser: false,
          text: 'Unable to process query: ${e.toString().replaceAll('Exception: ', '')}',
          intent: 'ERROR',
          confidence: 0.0,
          timestamp: DateTime.now(),
        ));
        _isQuerying = false;
      });
      _scrollToBottom();
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  IntelligenceBriefing _buildFallbackBriefing(String type) {
    final now = DateTime.now().toUtc().toIso8601String();
    final isLondon = type == 'london-open';
    return IntelligenceBriefing(
      briefingType: isLondon ? 'LONDON_OPEN' : 'DAILY_REVIEW',
      title: isLondon
          ? 'Falcon London Open Intelligence Briefing (Offline / Cached)'
          : 'Falcon Daily Performance Review (Offline / Cached)',
      summary: isLondon
          ? 'Benchmark institutional Asian session ranges and liquidity pools loaded. Falcon non-custodial capital protection active.'
          : 'Daily performance review loaded with benchmark risk guardrails and recovery headroom.',
      marketLevels: {
        'EUR/USD': {
          'current_price': 1.1350,
          'asian_high': 1.1375,
          'asian_low': 1.1320,
          'range_pips': 55.0,
          'tactical_bias': 'BULLISH_REVERSAL_POST_SWEEP',
        },
        'GBP/USD': {
          'current_price': 1.3270,
          'asian_high': 1.3300,
          'asian_low': 1.3240,
          'range_pips': 60.0,
          'tactical_bias': 'BULLISH_EXPANSION',
        },
        'XAU/USD': {
          'current_price': 4185.0,
          'asian_high': 4198.5,
          'asian_low': 4172.0,
          'range_dollars': 26.5,
          'tactical_bias': 'SNIPER_LONGS_DISCOUNT',
        },
      },
      keyInsights: [
        'Cloud server connection retry available via top action bar.',
        'Asian session manipulation phase monitored for liquidity sweep entries.',
        'Capital Guardian actively enforcing dynamic capital preservation and profit reserves.',
      ],
      riskState: {
        'consecutive_losses': 0,
        'profit_recovery_multiplier': 1.0,
        'max_entertaining_loss': 999999.0,
        'loss_ceiling_headroom': 999999.0,
        'recovery_status': 'BASELINE_1X',
      },
      formattedText: 'Falcon offline benchmark report. Tap Retry to fetch live cloud intelligence.',
      generatedAt: now,
    );
  }

  SessionBreakoutStructureData _buildFallbackSession(String symbol) {
    final isGold = symbol.toUpperCase().contains('XAU') || symbol.toUpperCase().contains('GOLD');
    final isGbp = symbol.toUpperCase().contains('GBP');
    return SessionBreakoutStructureData(
      symbol: symbol,
      timeframe: '15m',
      sessionRanges: [
        SessionRangeOverlay(
          sessionName: 'ASIAN',
          high: isGold ? 4185.0 : (isGbp ? 1.3300 : 1.1375),
          low: isGold ? 4172.0 : (isGbp ? 1.3240 : 1.1320),
          openPrice: isGold ? 4175.0 : (isGbp ? 1.3250 : 1.1330),
          closePrice: isGold ? 4182.0 : (isGbp ? 1.3290 : 1.1365),
          status: 'INTACT',
          rangePips: isGold ? 130.0 : 60.0,
        ),
        SessionRangeOverlay(
          sessionName: 'LONDON',
          high: isGold ? 4198.0 : (isGbp ? 1.3325 : 1.1395),
          low: isGold ? 4168.0 : (isGbp ? 1.3220 : 1.1305),
          openPrice: isGold ? 4182.0 : (isGbp ? 1.3290 : 1.1365),
          closePrice: isGold ? 4195.0 : (isGbp ? 1.3320 : 1.1385),
          status: 'BROKEN_UP',
          rangePips: isGold ? 300.0 : 105.0,
        ),
      ],
      volumeExpansions: [
        VolumeExpansionOverlay(
          timestamp: DateTime.now(),
          direction: 'BULLISH',
          rvol: 2.4,
          breakoutPrice: isGold ? 4188.0 : (isGbp ? 1.3305 : 1.1380),
          targetPrice: isGold ? 4210.0 : (isGbp ? 1.3360 : 1.1420),
          invalidationPrice: isGold ? 4172.0 : (isGbp ? 1.3240 : 1.1320),
          spreadRatio: 0.72,
        ),
      ],
      volatilityZone: VolatilityZoneOverlay(
        upperBand: isGold ? 4205.0 : (isGbp ? 1.3350 : 1.1420),
        lowerBand: isGold ? 4165.0 : (isGbp ? 1.3210 : 1.1290),
        meanLevel: isGold ? 4185.0 : (isGbp ? 1.3280 : 1.1355),
        currentSigma: 1.1,
        isExhausted: false,
        exhaustionState: 'NORMAL',
        rsiValue: 56.4,
      ),
      activeSession: 'LONDON',
      isBreakoutConfirmed: true,
    );
  }

  Widget _buildErrorBanner(String error, VoidCallback onRetry) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.warning.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.warning.withValues(alpha: 0.4)),
      ),
      child: Row(
        children: [
          const Icon(Icons.cloud_off_rounded, color: AppColors.warning, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              error,
              style: const TextStyle(color: AppColors.warning, fontSize: 11),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: 6),
          TextButton(
            onPressed: onRetry,
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              minimumSize: Size.zero,
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: const Text('Retry', style: TextStyle(color: AppColors.primary, fontSize: 12, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  Future<void> _loadBriefing() async {
    setState(() {
      _isLoadingBriefing = true;
      _briefingError = null;
    });
    try {
      IntelligenceBriefing briefing;
      if (_selectedBriefingType == 'london-open') {
        briefing = await _apiService.getLondonOpenBriefing();
      } else if (_selectedBriefingType == 'daily-review') {
        briefing = await _apiService.getDailyReviewBriefing();
      } else {
        briefing = await _apiService.getLatestBriefing();
      }
      if (!mounted) return;
      setState(() {
        _currentBriefing = briefing;
        _briefingError = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _briefingError = 'Could not load live briefing: ${e.toString().replaceAll("Exception:", "").trim()}';
        _currentBriefing ??= _buildFallbackBriefing(_selectedBriefingType);
      });
    } finally {
      if (mounted) setState(() => _isLoadingBriefing = false);
    }
  }

  Future<void> _loadSessionStructure() async {
    setState(() {
      _isLoadingSession = true;
      _sessionError = null;
    });
    try {
      final data = await _apiService.getSessionBreakoutStructure(symbol: _sessionSymbol);
      if (!mounted) return;
      setState(() {
        _sessionData = data;
        _sessionError = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _sessionError = 'Could not load live session structure: ${e.toString().replaceAll("Exception:", "").trim()}';
        _sessionData ??= _buildFallbackSession(_sessionSymbol);
      });
    } finally {
      if (mounted) setState(() => _isLoadingSession = false);
    }
  }


  Future<void> _dispatchToTelegram() async {
    setState(() => _isDispatchingTelegram = true);
    try {
      final res = await _apiService.dispatchBriefingToTelegram(
        briefingType: _selectedBriefingType,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(res['delivered'] == true
              ? 'Briefing dispatched to Telegram successfully!'
              : 'Telegram dispatch skipped: ${res['reason'] ?? 'check credentials'}'),
          backgroundColor: res['delivered'] == true ? AppColors.success : AppColors.warning,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Dispatch failed: $e'),
          backgroundColor: AppColors.error,
        ),
      );
    } finally {
      if (mounted) setState(() => _isDispatchingTelegram = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            Icon(Icons.auto_awesome, color: AppColors.primary, size: 22),
            SizedBox(width: 8),
            Text('Falcon AI Co-Pilot'),
          ],
        ),
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: AppColors.primary,
          labelColor: AppColors.primary,
          unselectedLabelColor: AppColors.textSecondary,
          tabs: const [
            Tab(icon: Icon(Icons.chat_outlined), text: 'AI Co-Pilot'),
            Tab(icon: Icon(Icons.newspaper_outlined), text: 'Briefings & Sessions'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildChatTab(),
          _buildBriefingsAndSessionsTab(),
        ],
      ),
    );
  }

  // ── Tab 1: AI Co-Pilot Chat ──────────────────────────────────────────────

  Widget _buildChatTab() {
    return Column(
      children: [
        // Quick prompts bar
        Container(
          height: 48,
          margin: const EdgeInsets.symmetric(vertical: 6),
          child: ListView.separated(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            scrollDirection: Axis.horizontal,
            itemCount: _quickPrompts.length,
            separatorBuilder: (_, __) => const SizedBox(width: 8),
            itemBuilder: (context, index) {
              final prompt = _quickPrompts[index];
              return ActionChip(
                label: Text(
                  prompt,
                  style: const TextStyle(fontSize: 12, color: AppColors.textPrimary),
                ),
                backgroundColor: AppColors.surfaceLight,
                side: BorderSide(color: AppColors.primary.withValues(alpha: 0.3)),
                onPressed: () => _sendQuery(prompt),
              );
            },
          ),
        ),

        // Messages list
        Expanded(
          child: ListView.builder(
            controller: _scrollController,
            padding: const EdgeInsets.all(12),
            itemCount: _messages.length,
            itemBuilder: (context, index) {
              final msg = _messages[index];
              return _buildMessageBubble(msg);
            },
          ),
        ),

        if (_isQuerying)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.primary),
                ),
                const SizedBox(width: 10),
                Text(
                  'Falcon is analyzing market context & regime memory...',
                  style: TextStyle(fontSize: 12, color: AppColors.textSecondary, fontStyle: FontStyle.italic),
                ),
              ],
            ),
          ),

        // Input bar
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: AppColors.surface,
            border: Border(top: BorderSide(color: Colors.white.withValues(alpha: 0.08))),
          ),
          child: SafeArea(
            child: Row(
              children: [
                // Symbol quick selector
                DropdownButton<String>(
                  value: _selectedSymbol,
                  dropdownColor: AppColors.surface,
                  underline: const SizedBox(),
                  style: const TextStyle(color: AppColors.primary, fontSize: 13, fontWeight: FontWeight.bold),
                  items: const [
                    DropdownMenuItem(value: 'XAUUSD', child: Text('XAU')),
                    DropdownMenuItem(value: 'EURUSD', child: Text('EUR')),
                    DropdownMenuItem(value: 'GBPUSD', child: Text('GBP')),
                    DropdownMenuItem(value: 'GBPJPY', child: Text('GJ')),
                    DropdownMenuItem(value: 'USDJPY', child: Text('UJ')),
                    DropdownMenuItem(value: 'AUDUSD', child: Text('AUD')),
                  ],
                  onChanged: (val) {
                    if (val != null) setState(() => _selectedSymbol = val);
                  },
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    controller: _queryController,
                    decoration: InputDecoration(
                      hintText: 'Ask Falcon Co-Pilot...',
                      hintStyle: const TextStyle(color: AppColors.textTertiary, fontSize: 14),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      filled: true,
                      fillColor: AppColors.surfaceLight,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: BorderSide.none,
                      ),
                    ),
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
                    onSubmitted: _sendQuery,
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  icon: const Icon(Icons.send_rounded, color: AppColors.primary),
                  onPressed: _isQuerying ? null : () => _sendQuery(_queryController.text),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildMessageBubble(_ChatMessage msg) {
    if (msg.isUser) {
      return Align(
        alignment: Alignment.centerRight,
        child: Container(
          margin: const EdgeInsets.only(bottom: 12, left: 48),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: AppColors.primary.withValues(alpha: 0.2),
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(16),
              topRight: Radius.circular(16),
              bottomLeft: Radius.circular(16),
            ),
            border: Border.all(color: AppColors.primary.withValues(alpha: 0.4)),
          ),
          child: Text(
            msg.text,
            style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
          ),
        ),
      );
    }

    // Falcon Co-Pilot response bubble
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 14, right: 32),
        child: AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: AppColors.primary.withValues(alpha: 0.2),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.auto_awesome, color: AppColors.primary, size: 16),
                  ),
                  const SizedBox(width: 8),
                  const Text(
                    'Falcon Intelligence',
                    style: TextStyle(
                      color: AppColors.primary,
                      fontSize: 13,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const Spacer(),
                  if (msg.intent != null)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.info.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        msg.intent!,
                        style: const TextStyle(color: AppColors.info, fontSize: 10, fontWeight: FontWeight.bold),
                      ),
                    ),
                  if (msg.confidence != null && msg.confidence! > 0) ...[
                    const SizedBox(width: 6),
                    Text(
                      '${(msg.confidence! * 100).toInt()}% conf',
                      style: const TextStyle(color: AppColors.textTertiary, fontSize: 10),
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 10),
              Text(
                msg.text,
                style: const TextStyle(color: AppColors.textPrimary, fontSize: 14, height: 1.4),
              ),

              // Technical context chip breakdown
              if (msg.technicalContext != null && msg.technicalContext!.isNotEmpty) ...[
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppColors.surfaceLight,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Technical Context',
                        style: TextStyle(color: AppColors.textSecondary, fontSize: 11, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 4),
                      Wrap(
                        spacing: 8,
                        runSpacing: 4,
                        children: msg.technicalContext!.entries.map((entry) {
                          return Text(
                            '${entry.key}: ${entry.value}',
                            style: const TextStyle(color: AppColors.primary, fontSize: 11),
                          );
                        }).toList(),
                      ),
                    ],
                  ),
                ),
              ],

              // Risk context breakdown
              if (msg.riskContext != null && msg.riskContext!.isNotEmpty) ...[
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppColors.warning.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: AppColors.warning.withValues(alpha: 0.3)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.shield_outlined, color: AppColors.warning, size: 16),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          'Recovery Multiplier: ${msg.riskContext!['recovery_multiplier'] ?? '1.0x'} | Risk Headroom: \$${msg.riskContext!['remaining_loss_headroom'] ?? 'Active'}',
                          style: const TextStyle(color: AppColors.warning, fontSize: 11, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  // ── Tab 2: Intelligence Briefings & Session Corridors ─────────────────────

  Widget _buildBriefingsAndSessionsTab() {
    return RefreshIndicator(
      onRefresh: () async {
        await Future.wait([_loadBriefing(), _loadSessionStructure()]);
      },
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Briefing Type Segment
            Row(
              children: [
                Expanded(
                  child: SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(value: 'latest', label: Text('Latest', style: TextStyle(fontSize: 11))),
                      ButtonSegment(value: 'london-open', label: Text('London Open', style: TextStyle(fontSize: 11))),
                      ButtonSegment(value: 'daily-review', label: Text('Daily Review', style: TextStyle(fontSize: 11))),
                    ],
                    selected: {_selectedBriefingType},
                    onSelectionChanged: (set) {
                      setState(() => _selectedBriefingType = set.first);
                      _loadBriefing();
                    },
                    style: SegmentedButton.styleFrom(
                      selectedBackgroundColor: AppColors.primary.withValues(alpha: 0.2),
                      selectedForegroundColor: AppColors.primary,
                      foregroundColor: AppColors.textSecondary,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Telegram Action Bar
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _isDispatchingTelegram ? null : _dispatchToTelegram,
                    icon: _isDispatchingTelegram
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.info),
                          )
                        : const Icon(Icons.send_rounded, color: AppColors.info, size: 18),
                    label: const Text('Dispatch Briefing to Telegram', style: TextStyle(color: AppColors.info)),
                    style: OutlinedButton.styleFrom(
                      side: BorderSide(color: AppColors.info.withValues(alpha: 0.4)),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Briefing Content Card
            if (_briefingError != null)
              _buildErrorBanner(_briefingError!, _loadBriefing),
            if (_isLoadingBriefing)
              const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()))
            else if (_currentBriefing != null)
              _buildBriefingCard(_currentBriefing!)
            else
              const AppCard(
                child: Center(
                  child: Text('No briefing available for selected period.', style: TextStyle(color: AppColors.textSecondary)),
                ),
              ),

            const SizedBox(height: 24),

            // Session Corridors & Volatility Section
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Session Breakouts & Volatility',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                ),
                DropdownButton<String>(
                  value: _sessionSymbol,
                  dropdownColor: AppColors.surface,
                  underline: const SizedBox(),
                  style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.bold),
                  items: const [
                    DropdownMenuItem(value: 'EURUSD', child: Text('EUR/USD')),
                    DropdownMenuItem(value: 'GBPUSD', child: Text('GBP/USD')),
                    DropdownMenuItem(value: 'GBPJPY', child: Text('GBP/JPY')),
                    DropdownMenuItem(value: 'USDJPY', child: Text('USD/JPY')),
                    DropdownMenuItem(value: 'AUDUSD', child: Text('AUD/USD')),
                    DropdownMenuItem(value: 'XAUUSD', child: Text('Gold (XAU)')),
                  ],
                  onChanged: (val) {
                    if (val != null) {
                      setState(() => _sessionSymbol = val);
                      _loadSessionStructure();
                    }
                  },
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (_sessionError != null)
              _buildErrorBanner(_sessionError!, _loadSessionStructure),
            if (_isLoadingSession)
              const Center(child: Padding(padding: EdgeInsets.all(16), child: CircularProgressIndicator()))
            else if (_sessionData != null)
              _buildSessionCard(_sessionData!)
            else
              const AppCard(
                child: Center(child: Text('Session structure data unavailable.', style: TextStyle(color: AppColors.textSecondary))),
              ),

          ],
        ),
      ),
    );
  }

  Widget _buildBriefingCard(IntelligenceBriefing briefing) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.article_outlined, color: AppColors.primary, size: 22),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      briefing.title,
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      briefing.generatedAt,
                      style: const TextStyle(fontSize: 11, color: AppColors.textTertiary),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            briefing.summary,
            style: const TextStyle(fontSize: 13, color: AppColors.textSecondary, height: 1.4),
          ),
          if (briefing.keyInsights.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text(
              'Key Institutional Insights',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
            ),
            const SizedBox(height: 8),
            ...briefing.keyInsights.map((insight) => Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.arrow_right_rounded, color: AppColors.primary, size: 20),
                      const SizedBox(width: 4),
                      Expanded(
                        child: Text(
                          insight,
                          style: const TextStyle(fontSize: 12, color: AppColors.textPrimary),
                        ),
                      ),
                    ],
                  ),
                )),
          ],
          if (briefing.riskState.isNotEmpty) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.surfaceLight,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.white.withValues(alpha: 0.05)),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  _buildMetric('Consecutive Losses', '${briefing.riskState['consecutive_losses'] ?? 0}'),
                  _buildMetric('Recovery Target', '${briefing.riskState['recovery_multiplier'] ?? '1.0'}x'),
                  _buildMetric('Risk Headroom', briefing.riskState['remaining_streak_loss_headroom'] != null ? '\$${briefing.riskState['remaining_streak_loss_headroom']}' : 'Unrestricted'),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildSessionCard(SessionBreakoutStructureData data) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '${data.symbol} • ${data.timeframe.toUpperCase()}',
                style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.primary),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text('${data.activeSession} ACTIVE', style: const TextStyle(color: AppColors.primary, fontSize: 10, fontWeight: FontWeight.bold)),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _buildSessionBox(
                  'Session Corridors',
                  '${data.sessionRanges.length}',
                  data.isBreakoutConfirmed ? 'Breakout Confirmed' : 'Range Intact',
                  Icons.view_column_outlined,
                  const Color(0xFF06B6D4),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildSessionBox(
                  '2.5σ Volatility',
                  data.volatilityZone?.exhaustionState ?? 'NORMAL',
                  data.volatilityZone != null ? 'RSI: ${data.volatilityZone!.rsiValue.toStringAsFixed(1)}' : 'Envelope Calibrated',
                  Icons.stacked_line_chart,
                  const Color(0xFF818CF8),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSessionBox(String title, String count, String subtitle, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: color, size: 18),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(fontSize: 11, color: AppColors.textSecondary),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            count,
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: color),
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 2),
          Text(
            subtitle,
            style: const TextStyle(fontSize: 10, color: AppColors.textTertiary),
          ),
        ],
      ),
    );
  }

  Widget _buildMetric(String label, String value) {
    return Column(
      children: [
        Text(value, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.primary)),
        const SizedBox(height: 2),
        Text(label, style: const TextStyle(fontSize: 10, color: AppColors.textSecondary)),
      ],
    );
  }
}
