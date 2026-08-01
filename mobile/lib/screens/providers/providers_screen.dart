import 'package:flutter/material.dart';
import '../../services/api/api_service.dart';
import '../../models/provider_models.dart';
import '../../widgets/cards/app_card.dart';
import '../../widgets/typography/section_title.dart';
import '../../widgets/loading/placeholder_card.dart';
import '../../core/constants/app_colors.dart';
import 'package:intl/intl.dart';

class ProvidersScreen extends StatefulWidget {
  const ProvidersScreen({super.key});

  @override
  State<ProvidersScreen> createState() => _ProvidersScreenState();
}

class _ProvidersScreenState extends State<ProvidersScreen> {
  final ApiService _apiService = ApiService();
  late Future<ProviderListResponse> _providersFuture;

  @override
  void initState() {
    super.initState();
    _fetchProviders();
  }

  void _fetchProviders() {
    setState(() {
      _providersFuture = _apiService.getProviders();
    });
  }

  Future<void> _handleRefresh() async {
    _fetchProviders();
    try {
      await _providersFuture;
    } catch (e) {
      // Ignored
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Provider Framework'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _handleRefresh,
          ),
        ],
      ),
      body: FutureBuilder<ProviderListResponse>(
        future: _providersFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Padding(
              padding: EdgeInsets.all(16.0),
              child: PlaceholderCard(height: 300),
            );
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
                      'Failed to load providers',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
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
                      onPressed: _fetchProviders,
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              ),
            );
          } else if (snapshot.hasData) {
            final data = snapshot.data!;
            return RefreshIndicator(
              onRefresh: _handleRefresh,
              child: ListView(
                padding: const EdgeInsets.all(16.0),
                children: [
                  _buildSummaryCards(data.summary),
                  const SizedBox(height: 24),
                  const SectionTitle(
                    title: 'Registered Providers',
                    subtitle: 'Live data connections',
                  ),
                  const SizedBox(height: 16),
                  ...data.providers.map((p) => _buildProviderCard(p)),
                ],
              ),
            );
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }

  Widget _buildSummaryCards(ProviderSummary summary) {
    return Row(
      children: [
        Expanded(
          child: AppCard(
            child: Column(
              children: [
                const Text(
                  'Total',
                  style: TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  summary.totalProviders.toString(),
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: AppCard(
            child: Column(
              children: [
                const Text(
                  'Online',
                  style: TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  summary.online.toString(),
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: AppColors.success,
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: AppCard(
            child: Column(
              children: [
                const Text(
                  'Degraded',
                  style: TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  summary.degraded.toString(),
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: AppColors.warning,
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: AppCard(
            child: Column(
              children: [
                const Text(
                  'Offline',
                  style: TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  summary.offline.toString(),
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: AppColors.error,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildProviderCard(ProviderSnapshot snapshot) {
    final meta = snapshot.metadata;
    final stat = snapshot.statistics;
    final isOnline = meta.status == ProviderStatus.ONLINE;

    return Padding(
      padding: const EdgeInsets.only(bottom: 16.0),
      child: AppCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        meta.providerName,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'ID: ${meta.providerId} • v${meta.providerVersion}',
                        style: const TextStyle(
                          fontSize: 13,
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: (isOnline
                            ? AppColors.success
                            : (meta.status == ProviderStatus.DEGRADED
                                ? AppColors.warning
                                : AppColors.error))
                        .withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: (isOnline
                              ? AppColors.success
                              : (meta.status == ProviderStatus.DEGRADED
                                  ? AppColors.warning
                                  : AppColors.error))
                          .withValues(alpha: 0.2),
                    ),
                  ),
                  child: Text(
                    meta.status.name,
                    style: TextStyle(
                      color: isOnline
                          ? AppColors.success
                          : (meta.status == ProviderStatus.DEGRADED
                              ? AppColors.warning
                              : AppColors.error),
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
            Divider(height: 32, color: Colors.grey.withValues(alpha: 0.2)),
            Row(
              children: [
                _buildStatColumn('Latency (avg)', '${snapshot.latency.averageMs.toStringAsFixed(1)} ms'),
                _buildStatColumn('Success Rate', '${stat.successRate.toStringAsFixed(1)}%'),
                _buildStatColumn('Health', meta.health.name),
              ],
            ),
            const SizedBox(height: 16),
            const Text(
              'Capabilities',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: meta.capabilities.map((c) {
                return Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppColors.surfaceLight,
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: Colors.grey.withValues(alpha: 0.2)),
                  ),
                  child: Text(
                    c.name,
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppColors.textPrimary,
                    ),
                  ),
                );
              }).toList(),
            ),
            if (snapshot.lastHeartbeat != null) ...[
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Last Heartbeat: ${DateFormat('HH:mm:ss').format(snapshot.lastHeartbeat!.toLocal())}',
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.textTertiary,
                    ),
                  ),
                  if (snapshot.lastSuccessfulUpdate != null)
                    Text(
                      'Update: ${DateFormat('HH:mm:ss').format(snapshot.lastSuccessfulUpdate!.toLocal())}',
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppColors.textTertiary,
                      ),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildStatColumn(String label, String value) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
        ],
      ),
    );
  }
}
