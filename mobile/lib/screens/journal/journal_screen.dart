import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants/app_colors.dart';
import '../../core/utils/price_formatter.dart';
import '../../models/strategy_model.dart';
import '../../models/trade_journal.dart';
import '../../models/candle_data.dart';
import '../../services/api/api_service.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/chips/status_chip.dart';
import '../../widgets/loading/placeholder_card.dart';

class JournalScreen extends StatefulWidget {
  const JournalScreen({super.key});

  @override
  State<JournalScreen> createState() => _JournalScreenState();
}

class _JournalScreenState extends State<JournalScreen> {
  late Future<TradeJournalListResponse> _journalFuture;
  final ApiService _apiService = ApiService();

  @override
  void initState() {
    super.initState();
    _fetchJournal();
  }

  void _fetchJournal() {
    ApiService.invalidateTradeJournalCache();
    setState(() {
      _journalFuture = _apiService.getTradeJournal();
    });
  }

  void _notify(String message) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _addTrade() async {
    final draft = await showDialog<TradeJournalDraft>(
      context: context,
      builder: (context) => const _NewTradeDialog(),
    );
    if (draft == null) return;
    try {
      await _apiService.createTradeJournal(draft);
    } catch (e) {
      if (!mounted) return;
      _notify('Could not save trade: ${e.toString().replaceAll('Exception: ', '')}');
      return;
    }
    if (!mounted) return;
    _fetchJournal();
  }

  Future<void> _closeTrade(TradeJournalItem trade) async {
    final close = await showDialog<TradeJournalClose>(
      context: context,
      builder: (context) => _CloseTradeDialog(trade: trade),
    );
    if (close == null) return;
    try {
      await _apiService.closeTradeJournal(trade.id, close);
    } catch (e) {
      if (!mounted) return;
      _notify('Could not close trade: ${e.toString().replaceAll('Exception: ', '')}');
      return;
    }
    if (!mounted) return;
    _fetchJournal();
  }

  Future<void> _handleRefresh() async {
    _fetchJournal();
    try {
      await _journalFuture;
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Trade Journal'),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _addTrade,
        tooltip: 'Log trade',
        child: const Icon(Icons.add),
      ),
      body: RefreshIndicator(
        onRefresh: _handleRefresh,
        child: FutureBuilder<TradeJournalListResponse>(
          future: _journalFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: 4,
                itemBuilder: (context, index) => const Padding(
                  padding: EdgeInsets.only(bottom: 16),
                  child: PlaceholderCard(height: 160),
                ),
              );
            } else if (snapshot.hasError) {
              return Center(
                child: Padding(
                  padding: const EdgeInsets.all(24.0),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.error_outline, color: AppColors.error, size: 64),
                      const SizedBox(height: 16),
                      Text(
                        'Failed to load journal',
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                              fontWeight: FontWeight.bold,
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
                        onPressed: _fetchJournal,
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                ),
              );
            } else if (snapshot.hasData) {
              final trades = snapshot.data!.trades;
              if (trades.isEmpty) {
                return const Center(
                  child: Text(
                    'No journal entries yet. Log a trade to start tracking.',
                    style: TextStyle(color: AppColors.textSecondary),
                  ),
                );
              }
              return ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: trades.length,
                itemBuilder: (context, index) {
                  final trade = trades[index];
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: _buildTradeCard(trade),
                  );
                },
              );
            } else {
              return const SizedBox.shrink();
            }
          },
        ),
      ),
    );
  }

  Widget _buildTradeCard(TradeJournalItem trade) {
    final isBuy = trade.direction.toUpperCase() == 'BUY';
    final dateFormat = DateFormat('MMM dd, yyyy HH:mm');
    
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: isBuy
                          ? AppColors.success.withValues(alpha: 0.1)
                          : AppColors.error.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Text(
                      isBuy ? '🟢 BUY' : '🔴 SELL',
                      style: TextStyle(
                        color: isBuy ? AppColors.success : AppColors.error,
                        fontWeight: FontWeight.bold,
                        fontSize: 12,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    trade.symbol,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ],
              ),
              StatusChip(
                status: trade.result,
                type: StatusChipType.journalResult,
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildValueColumn('Entry', PriceFormatter.format(trade.symbol, trade.entryPrice)),
              _buildValueColumn('Exit', trade.exitPrice != null ? PriceFormatter.format(trade.symbol, trade.exitPrice!) : '-'),
              _buildValueColumn(
                'P/L',
                '${trade.profitLoss >= 0 ? '+' : ''}${trade.profitLoss.toStringAsFixed(2)}',
                color: trade.profitLoss > 0
                    ? AppColors.success
                    : (trade.profitLoss < 0 ? AppColors.error : AppColors.warning),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Divider(color: AppColors.surfaceLight),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  'Date: ${dateFormat.format(trade.tradeDate.toLocal())}',
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 12,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(width: 8),
              StatusChip(
                status: trade.status,
                type: StatusChipType.journalStatus,
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              OutlinedButton.icon(
                onPressed: () {
                  final isBuy = trade.direction.toUpperCase() == 'BUY';
                  final overlay = TradeCorridorOverlay(
                    entry: trade.entryPrice,
                    stopLoss: trade.stopLoss,
                    takeProfit: trade.takeProfit,
                    isBuy: isBuy,
                    status: trade.status,
                    isBreakeven: trade.status.toUpperCase() == 'BREAKEVEN',
                    breakevenPrice: trade.status.toUpperCase() == 'BREAKEVEN' ? trade.entryPrice : null,
                    entryTime: trade.tradeDate,
                  );

                  context.push(
                    '/chart?symbol=${trade.symbol}&timeframe=${trade.timeframe}',
                    extra: {
                      'tradeOverlay': overlay,
                      'strategyName': trade.strategyId,
                      'conviction': trade.confidence,
                    },
                  );
                },
                icon: const Icon(Icons.candlestick_chart_rounded, size: 15, color: AppColors.primary),
                label: const Text('Chart View', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                style: OutlinedButton.styleFrom(
                  side: BorderSide(color: AppColors.primary.withValues(alpha: 0.4)),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  minimumSize: const Size(0, 32),
                ),
              ),
              if (trade.status.toUpperCase() != 'CLOSED')
                TextButton.icon(
                  onPressed: () => _closeTrade(trade),
                  icon: const Icon(Icons.flag_outlined, size: 16),
                  label: const Text('Close trade', style: TextStyle(fontSize: 12)),
                  style: TextButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    minimumSize: const Size(0, 32),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildValueColumn(String label, String value, {Color? color}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: AppColors.textSecondary,
            fontSize: 12,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            fontWeight: FontWeight.bold,
            color: color ?? AppColors.textPrimary,
            fontSize: 15,
          ),
        ),
      ],
    );
  }
}

class _NewTradeDialog extends StatefulWidget {
  const _NewTradeDialog();

  @override
  State<_NewTradeDialog> createState() => _NewTradeDialogState();
}

class _NewTradeDialogState extends State<_NewTradeDialog> {
  final _formKey = GlobalKey<FormState>();
  final _symbol = TextEditingController(text: 'XAU/USD');
  final _entryPrice = TextEditingController();
  final _stopLoss = TextEditingController();
  final _takeProfit = TextEditingController();
  final _timeframe = TextEditingController(text: 'H1');
  final _marketSession = TextEditingController(text: 'London');
  final _confidence = TextEditingController(text: '70');
  final _reason = TextEditingController();
  String _direction = 'BUY';
  String? _strategyId;
  List<StrategyItem> _strategies = [];

  @override
  void initState() {
    super.initState();
    ApiService().getStrategies().then((response) {
      if (mounted) setState(() => _strategies = response.strategies);
    }).catchError((_) {});
  }

  @override
  void dispose() {
    _symbol.dispose();
    _entryPrice.dispose();
    _stopLoss.dispose();
    _takeProfit.dispose();
    _timeframe.dispose();
    _marketSession.dispose();
    _confidence.dispose();
    _reason.dispose();
    super.dispose();
  }

  double get _riskReward {
    final entry = double.tryParse(_entryPrice.text);
    final stop = double.tryParse(_stopLoss.text);
    final target = double.tryParse(_takeProfit.text);
    if (entry == null || stop == null || target == null) return 0;
    final risk = (entry - stop).abs();
    return risk == 0 ? 0 : double.parse(((target - entry).abs() / risk).toStringAsFixed(2));
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    Navigator.of(context).pop(
      TradeJournalDraft(
        strategyId: _strategyId,
        symbol: _symbol.text.trim(),
        direction: _direction,
        entryPrice: double.parse(_entryPrice.text),
        stopLoss: double.parse(_stopLoss.text),
        takeProfit: double.parse(_takeProfit.text),
        timeframe: _timeframe.text.trim(),
        marketSession: _marketSession.text.trim(),
        tradeDate: DateTime.now(),
        riskReward: _riskReward,
        confidence: (double.tryParse(_confidence.text)?.round() ?? 0).clamp(0, 100),
        reasonForEntry: _reason.text.trim(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Log trade'),
      content: SingleChildScrollView(
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _textField(_symbol, 'Symbol'),
              if (_strategies.isNotEmpty)
                DropdownButtonFormField<String?>(
                  initialValue: _strategyId,
                  decoration: const InputDecoration(labelText: 'Strategy'),
                  items: [
                    const DropdownMenuItem<String?>(
                      value: null,
                      child: Text('No strategy'),
                    ),
                    ..._strategies.map(
                      (strategy) => DropdownMenuItem<String?>(
                        value: strategy.id,
                        child: Text(strategy.name),
                      ),
                    ),
                  ],
                  onChanged: (value) => setState(() => _strategyId = value),
                ),
              DropdownButtonFormField<String>(
                initialValue: _direction,
                decoration: const InputDecoration(labelText: 'Direction'),
                items: const [
                  DropdownMenuItem(value: 'BUY', child: Text('BUY')),
                  DropdownMenuItem(value: 'SELL', child: Text('SELL')),
                ],
                onChanged: (value) => setState(() => _direction = value ?? 'BUY'),
              ),
              _textField(_entryPrice, 'Entry price', numeric: true),
              _textField(_stopLoss, 'Stop loss', numeric: true),
              _textField(_takeProfit, 'Take profit', numeric: true),
              _textField(_timeframe, 'Timeframe'),
              _textField(_marketSession, 'Market session'),
              _textField(_confidence, 'Confidence (0-100)', numeric: true),
              _textField(_reason, 'Reason for entry'),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        ElevatedButton(onPressed: _submit, child: const Text('Save')),
      ],
    );
  }
}

class _CloseTradeDialog extends StatefulWidget {
  const _CloseTradeDialog({required this.trade});

  final TradeJournalItem trade;

  @override
  State<_CloseTradeDialog> createState() => _CloseTradeDialogState();
}

class _CloseTradeDialogState extends State<_CloseTradeDialog> {
  final _formKey = GlobalKey<FormState>();
  final _exitPrice = TextEditingController();
  final _profitLoss = TextEditingController();
  final _reasonForExit = TextEditingController();
  final _lesson = TextEditingController();

  @override
  void dispose() {
    _exitPrice.dispose();
    _profitLoss.dispose();
    _reasonForExit.dispose();
    _lesson.dispose();
    super.dispose();
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    Navigator.of(context).pop(
      TradeJournalClose(
        exitPrice: double.parse(_exitPrice.text),
        profitLoss: double.parse(_profitLoss.text),
        closeDate: DateTime.now(),
        reasonForExit: _reasonForExit.text.trim().isEmpty ? null : _reasonForExit.text.trim(),
        lessonLearned: _lesson.text.trim().isEmpty ? null : _lesson.text.trim(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('Close ${widget.trade.symbol}'),
      content: SingleChildScrollView(
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _textField(_exitPrice, 'Exit price', numeric: true),
              _textField(_profitLoss, 'Profit / loss', numeric: true),
              _textField(_reasonForExit, 'Reason for exit', required: false),
              _textField(_lesson, 'Lesson learned', required: false),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        ElevatedButton(onPressed: _submit, child: const Text('Close trade')),
      ],
    );
  }
}

Widget _textField(
  TextEditingController controller,
  String label, {
  bool numeric = false,
  bool required = true,
}) {
  return TextFormField(
    controller: controller,
    decoration: InputDecoration(labelText: label),
    keyboardType: numeric
        ? const TextInputType.numberWithOptions(decimal: true, signed: true)
        : TextInputType.text,
    validator: (value) {
      final text = value?.trim() ?? '';
      if (text.isEmpty) return required ? 'Required' : null;
      if (numeric && double.tryParse(text) == null) return 'Enter a number';
      return null;
    },
  );
}
