import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../models/runtime_models.dart';
import '../../services/api/api_service.dart';

class RuntimeScreen extends StatefulWidget {
  const RuntimeScreen({Key? key}) : super(key: key);

  @override
  State<RuntimeScreen> createState() => _RuntimeScreenState();
}

class _RuntimeScreenState extends State<RuntimeScreen> {
  final ApiService _api = ApiService();
  RuntimeProvidersResponse? _providers;
  RuntimeEventsResponse? _events;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadRuntimeData();
  }

  Future<void> _loadRuntimeData() async {
    setState(() => _loading = true);
    try {
      final provResp = await _api.getRuntimeProviders();
      final evResp = await _api.getRuntimeEvents(limit: 50);

      final providers = RuntimeProvidersResponse.fromJson(provResp);
      final events = RuntimeEventsResponse.fromJson(evResp);

      setState(() {
        _providers = providers;
        _events = events;
        _error = null;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Failed to load runtime data: $e';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Runtime Diagnostics'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadRuntimeData,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Text(
                    _error!,
                    style: const TextStyle(color: Colors.red),
                  ),
                )
              : _buildContent(),
    );
  }

  Widget _buildContent() {
    if (_providers == null || _events == null) {
      return const Center(child: Text('No data available'));
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSummaryCard(),
          const SizedBox(height: 16),
          _buildProviderCards(),
          const SizedBox(height: 16),
          _buildTimelineSection(),
        ],
      ),
    );
  }

  Widget _buildSummaryCard() {
    final s = _providers!.summary;
    final uptime = Duration(seconds: s.uptimeSeconds.toInt());
    final uptimeStr =
        '${uptime.inHours}h ${uptime.inMinutes % 60}m ${uptime.inSeconds % 60}s';

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'System Summary',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            _summaryRow('Uptime', uptimeStr),
            _summaryRow('Total Requests', s.totalRequests.toString()),
            _summaryRow(
              'Success Rate',
              '${s.overallSuccessRate.toStringAsFixed(1)}%',
              color: s.overallSuccessRate > 95
                  ? Colors.green
                  : s.overallSuccessRate > 90
                      ? Colors.orange
                      : Colors.red,
            ),
            _summaryRow('Failovers', s.totalFailovers.toString()),
            _summaryRow(
              'Cache Hit Rate',
              '${s.overallCacheHitRate.toStringAsFixed(1)}%',
            ),
            _summaryRow('Circuit Breaker Opens', s.circuitBreakerOpens.toString()),
          ],
        ),
      ),
    );
  }

  Widget _summaryRow(String label, String value, {Color? color}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w500)),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProviderCards() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Provider Health',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        ..._providers!.providers
            .map(
              (p) => _buildProviderCard(p),
            )
            .toList(),
      ],
    );
  }

  Widget _buildProviderCard(RuntimeProviderHealth p) {
    final statusColor = _statusColor(p.status);
    final healthColor = _healthColor(p.health);

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  p.providerName,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: statusColor.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        p.status,
                        style: TextStyle(
                          color: statusColor,
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: healthColor.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        p.health,
                        style: TextStyle(
                          color: healthColor,
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 8),
            _providerStatRow('Success Rate', '${p.successRate.toStringAsFixed(1)}%'),
            _providerStatRow(
              'Latency (avg / P95)',
              '${p.avgLatencyMs.toStringAsFixed(1)} / ${p.p95LatencyMs.toStringAsFixed(1)} ms',
            ),
            _providerStatRow(
              'Circuit State',
              p.circuitBreakerState,
            ),
            if (p.consecutiveFailures > 0)
              _providerStatRow(
                'Consecutive Failures',
                p.consecutiveFailures.toString(),
                color: Colors.red,
              ),
            if (p.http429Count > 0)
              _providerStatRow(
                'HTTP 429 Count',
                p.http429Count.toString(),
                color: Colors.orange,
              ),
            if (p.recoveryCount > 0)
              _providerStatRow(
                'Recoveries',
                p.recoveryCount.toString(),
                color: Colors.green,
              ),
            if (p.lastSuccessAt != null)
              _providerStatRow(
                'Last Success',
                _formatTime(p.lastSuccessAt!),
              ),
            if (p.circuitRetryInSeconds != null)
              _providerStatRow(
                'Retry In',
                '${p.circuitRetryInSeconds!.toStringAsFixed(1)}s',
                color: Colors.orange,
              ),
          ],
        ),
      ),
    );
  }

  Widget _providerStatRow(
    String label,
    String value, {
    Color? color,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              color: Colors.grey,
            ),
          ),
          Text(
            value,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTimelineSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Recent Events (Timeline)',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        if (_events!.events.isEmpty)
          const Text('No events recorded yet')
        else
          ..._events!.events.take(20).map((e) => _buildTimelineEntry(e)).toList(),
      ],
    );
  }

  Widget _buildTimelineEntry(RuntimeTimelineEvent e) {
    final eventColor = _eventTypeColor(e.eventType);

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 70,
            child: Text(
              e.timeLabel,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${e.providerName}: ${e.eventType}',
                  style: TextStyle(
                    fontSize: 12,
                    color: eventColor,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                if (e.symbol != null)
                  Text(
                    e.symbol!,
                    style: const TextStyle(
                      fontSize: 10,
                      color: Colors.grey,
                    ),
                  ),
                if (e.detail.isNotEmpty)
                  Text(
                    e.detail,
                    style: const TextStyle(
                      fontSize: 10,
                      color: Colors.grey,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'ONLINE':
        return Colors.green;
      case 'DEGRADED':
        return Colors.orange;
      case 'RATE_LIMITED':
        return Colors.deepOrange;
      case 'OFFLINE':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  Color _healthColor(String health) {
    switch (health) {
      case 'HEALTHY':
        return Colors.green;
      case 'WARNING':
        return Colors.orange;
      case 'CRITICAL':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  Color _eventTypeColor(String eventType) {
    if (eventType.contains('Failed') || eventType.contains('Open'))
      return Colors.red;
    if (eventType.contains('Success') || eventType.contains('Closed'))
      return Colors.green;
    if (eventType.contains('RateLimited')) return Colors.orange;
    if (eventType.contains('Hit')) return Colors.blue;
    return Colors.grey;
  }

  String _formatTime(String isoTimestamp) {
    final parsed = DateTime.tryParse(isoTimestamp);
    if (parsed == null) return isoTimestamp;
    return DateFormat('HH:mm:ss').format(parsed.toLocal());
  }
}
