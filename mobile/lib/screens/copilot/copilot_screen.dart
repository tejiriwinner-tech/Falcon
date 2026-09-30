import 'package:flutter/material.dart';
import '../../services/api/api_service.dart';
import '../../models/copilot_models.dart';
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

  // SMC state
  SMCStructureData? _smcData;
  bool _isLoadingSMC = false;
  String _smcSymbol = 'EURUSD';
  String? _smcError;

  final List<String> _quickPrompts = [
    'Why did you trigger this Gold buy?',
    'What is our current streak and recovery headroom?',
    'What did you learn from the last loss?',
    'What is the active capital cycle?',
    'Explain the SMC order blocks for EURUSD',
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);

    // Initial Co-Pilot welcome message
    _messages.add(
      _ChatMessage(
        isUser: false,
        text: 'Greetings Trader. I am Falcon AI Co-Pilot—your institutional Smart Money, Forensic Learning, and Capital Guardian intelligence.\n\nAsk me about trade rationales, current streak recovery progress, forensic lessons committed to memory, or institutional SMC structures.',
        intent: 'GREETING',
        confidence: 1.0,
        timestamp: DateTime.now(),
      ),
    );

    _loadBriefing();
    _loadSMC();
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
        'Capital Guardian actively enforcing \$20.00 max entertaining streak ceiling.',
      ],
      riskState: {
        'consecutive_losses': 0,
        'profit_recovery_multiplier': 1.0,
        'max_entertaining_loss': 20.0,
        'loss_ceiling_headroom': 20.0,
        'recovery_status': 'BASELINE_1X',
      },
      formattedText: 'Falcon offline benchmark report. Tap Retry to fetch live cloud intelligence.',
      generatedAt: now,
    );
  }

  SMCStructureData _buildFallbackSMC(String symbol) {
    final isGold = symbol.toUpperCase().contains('XAU') || symbol.toUpperCase().contains('GOLD');
    final isGbp = symbol.toUpperCase().contains('GBP');
    return SMCStructureData(
      symbol: symbol,
      timeframe: '15m',
      totalOrderBlocks: 2,
      totalFairValueGaps: 1,
      unmitigatedOrderBlocks: 1,
      unmitigatedFairValueGaps: 1,
      orderBlocks: [
        {
          'symbol': symbol,
          'timeframe': '15m',
          'block_type': 'BULLISH',
          'high': isGold ? 4175.5 : (isGbp ? 1.3245 : 1.1335),
          'low': isGold ? 4171.0 : (isGbp ? 1.3235 : 1.1325),
          'is_mitigated': false,
        },
        {
          'symbol': symbol,
          'timeframe': '15m',
          'block_type': 'BEARISH',
          'high': isGold ? 4198.0 : (isGbp ? 1.3315 : 1.1385),
          'low': isGold ? 4195.0 : (isGbp ? 1.3300 : 1.1370),
          'is_mitigated': true,
        },
      ],
      fairValueGaps: [
        {
          'symbol': symbol,
          'timeframe': '15m',
          'gap_type': 'BULLISH',
          'top': isGold ? 4182.0 : (isGbp ? 1.3265 : 1.1348),
          'bottom': isGold ? 4178.0 : (isGbp ? 1.3255 : 1.1342),
          'is_mitigated': false,
        },
      ],
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

  Future<void> _loadSMC() async {
    setState(() {
      _isLoadingSMC = true;
      _smcError = null;
    });
    try {
      final data = await _apiService.getSMCStructure(symbol: _smcSymbol);
      if (!mounted) return;
      setState(() {
        _smcData = data;
        _smcError = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _smcError = 'Could not load live SMC structure: ${e.toString().replaceAll("Exception:", "").trim()}';
        _smcData ??= _buildFallbackSMC(_smcSymbol);
      });
    } finally {
      if (mounted) setState(() => _isLoadingSMC = false);
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
            Tab(icon: Icon(Icons.newspaper_outlined), text: 'Briefings & SMC'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildChatTab(),
          _buildBriefingsAndSMCTab(),
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
                    DropdownMenuItem(value: 'USDJPY', child: Text('JPY')),
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
                          'Recovery Multiplier: ${msg.riskContext!['recovery_multiplier'] ?? '1.0x'} | Streak Headroom: \$${msg.riskContext!['remaining_loss_headroom'] ?? '20.00'}',
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

  // ── Tab 2: Intelligence Briefings & SMC Structure ─────────────────────────

  Widget _buildBriefingsAndSMCTab() {
    return RefreshIndicator(
      onRefresh: () async {
        await Future.wait([_loadBriefing(), _loadSMC()]);
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

            // SMC Institutional Structure Section
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Smart Money Concepts (SMC)',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                ),
                DropdownButton<String>(
                  value: _smcSymbol,
                  dropdownColor: AppColors.surface,
                  underline: const SizedBox(),
                  style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.bold),
                  items: const [
                    DropdownMenuItem(value: 'EURUSD', child: Text('EUR/USD')),
                    DropdownMenuItem(value: 'GBPUSD', child: Text('GBP/USD')),
                    DropdownMenuItem(value: 'XAUUSD', child: Text('Gold (XAU)')),
                  ],
                  onChanged: (val) {
                    if (val != null) {
                      setState(() => _smcSymbol = val);
                      _loadSMC();
                    }
                  },
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (_smcError != null)
              _buildErrorBanner(_smcError!, _loadSMC),
            if (_isLoadingSMC)
              const Center(child: Padding(padding: EdgeInsets.all(16), child: CircularProgressIndicator()))
            else if (_smcData != null)
              _buildSMCCard(_smcData!)
            else
              const AppCard(
                child: Center(child: Text('SMC structure data unavailable.', style: TextStyle(color: AppColors.textSecondary))),
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
                  _buildMetric('Loss Headroom', '\$${briefing.riskState['remaining_streak_loss_headroom'] ?? '20.00'}'),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildSMCCard(SMCStructureData smc) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '${smc.symbol} • ${smc.timeframe.toUpperCase()}',
                style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.primary),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppColors.primary.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Text('Live Institutional Perception', style: TextStyle(color: AppColors.primary, fontSize: 10, fontWeight: FontWeight.bold)),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _buildSMCBox(
                  'Order Blocks (OB)',
                  '${smc.totalOrderBlocks}',
                  '${smc.unmitigatedOrderBlocks} Unmitigated',
                  Icons.layers_outlined,
                  AppColors.info,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildSMCBox(
                  'Fair Value Gaps (FVG)',
                  '${smc.totalFairValueGaps}',
                  '${smc.unmitigatedFairValueGaps} Open Gaps',
                  Icons.water_damage_outlined,
                  AppColors.warning,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSMCBox(String title, String count, String subtitle, IconData icon, Color color) {
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
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: color),
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
