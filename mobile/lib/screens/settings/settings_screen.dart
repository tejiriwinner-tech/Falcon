import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../core/constants/app_colors.dart';
import '../../widgets/typography/section_title.dart';
import '../../services/theme/theme_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _pushNotifications = true;
  bool _signalAlerts = true;
  bool _newsAlerts = false;
  String _selectedRisk = 'Medium';

  @override
  void initState() {
    super.initState();
    ThemeService().addListener(_onThemeChanged);
    _loadSettings();
  }

  @override
  void dispose() {
    ThemeService().removeListener(_onThemeChanged);
    super.dispose();
  }

  Future<void> _loadSettings() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      setState(() {
        _pushNotifications = prefs.getBool('settings_push_notifications') ?? true;
        _signalAlerts = prefs.getBool('settings_signal_alerts') ?? true;
        _newsAlerts = prefs.getBool('settings_news_alerts') ?? false;
        _selectedRisk = prefs.getString('settings_selected_risk') ?? 'Medium';
      });
    } catch (_) {}
  }

  Future<void> _updateSetting(String key, dynamic value) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      if (value is bool) {
        await prefs.setBool(key, value);
      } else if (value is String) {
        await prefs.setString(key, value);
      }
    } catch (_) {}
  }

  void _onThemeChanged() {
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Profile tile
          _buildProfileTile(),
          const SizedBox(height: 24),

          // Notifications
          const SectionTitle(title: 'Notifications'),
          const SizedBox(height: 12),
          _buildCard([
            _buildToggleTile(
              icon: Icons.notifications_outlined,
              title: 'Push Notifications',
              subtitle: 'Receive in-app alerts',
              value: _pushNotifications,
              onChanged: (v) {
                setState(() => _pushNotifications = v);
                _updateSetting('settings_push_notifications', v);
              },
            ),
            _buildDivider(),
            _buildToggleTile(
              icon: Icons.trending_up,
              title: 'Signal Alerts',
              subtitle: 'Notify on new active signals',
              value: _signalAlerts,
              onChanged: (v) {
                setState(() => _signalAlerts = v);
                _updateSetting('settings_signal_alerts', v);
              },
            ),
            _buildDivider(),
            _buildToggleTile(
              icon: Icons.newspaper_outlined,
              title: 'News Alerts',
              subtitle: 'High-impact economic news',
              value: _newsAlerts,
              onChanged: (v) {
                setState(() => _newsAlerts = v);
                _updateSetting('settings_news_alerts', v);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(v
                        ? '📰 News Alerts Enabled (High-impact event warnings)'
                        : 'News alerts muted'),
                    duration: const Duration(seconds: 2),
                    behavior: SnackBarBehavior.floating,
                  ),
                );
              },
            ),
          ]),
          const SizedBox(height: 24),

          // Risk Management
          const SectionTitle(title: 'Risk Management'),
          const SizedBox(height: 12),
          _buildCard([
            _buildRiskSelector(),
          ]),
          const SizedBox(height: 24),

          // Appearance
          const SectionTitle(title: 'Appearance'),
          const SizedBox(height: 12),
          _buildCard([
            _buildToggleTile(
              icon: Icons.dark_mode_outlined,
              title: 'Dark Mode',
              subtitle: 'Always-on dark theme',
              value: ThemeService().isDarkMode,
              onChanged: (v) => ThemeService().toggleTheme(),
            ),
          ]),
          const SizedBox(height: 24),

          // About
          const SectionTitle(title: 'About'),
          const SizedBox(height: 12),
          _buildCard([
            _buildInfoTile(icon: Icons.info_outline, title: 'Version', trailing: '1.0.0'),
            _buildDivider(),
            _buildInfoTile(icon: Icons.shield_outlined, title: 'Privacy Policy', trailing: ''),
            _buildDivider(),
            _buildInfoTile(icon: Icons.description_outlined, title: 'Terms of Service', trailing: ''),
          ]),
          const SizedBox(height: 32),

          // Disclaimer
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.textTertiary.withValues(alpha: 0.2)),
            ),
            child: const Text(
              'Falcon is an AI-powered signal assistant. All signals are for informational purposes only. Trade responsibly.',
              style: TextStyle(
                color: AppColors.textTertiary,
                fontSize: 12,
                height: 1.6,
              ),
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  Widget _buildProfileTile() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.15),
              shape: BoxShape.circle,
              border: Border.all(color: AppColors.primary, width: 1.5),
            ),
            child: const Icon(Icons.person, color: AppColors.primary, size: 28),
          ),
          const SizedBox(width: 16),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Falcon Trader',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
                  ),
                ),
                SizedBox(height: 2),
                Text(
                  'Pro Account',
                  style: TextStyle(color: AppColors.primary, fontSize: 13),
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right, color: AppColors.textTertiary),
        ],
      ),
    );
  }

  Widget _buildCard(List<Widget> children) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(children: children),
    );
  }

  Widget _buildToggleTile({
    required IconData icon,
    required String title,
    required String subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return ListTile(
      leading: Icon(icon, color: AppColors.primary, size: 22),
      title: Text(title, style: const TextStyle(color: AppColors.textPrimary, fontSize: 15)),
      subtitle: Text(subtitle, style: const TextStyle(color: AppColors.textTertiary, fontSize: 12)),
      trailing: Switch.adaptive(
        value: value,
        onChanged: onChanged,
        activeTrackColor: AppColors.primary,
      ),
    );
  }

  Widget _buildInfoTile({required IconData icon, required String title, required String trailing}) {
    return ListTile(
      leading: Icon(icon, color: AppColors.primary, size: 22),
      title: Text(title, style: const TextStyle(color: AppColors.textPrimary, fontSize: 15)),
      trailing: trailing.isNotEmpty
          ? Text(trailing, style: const TextStyle(color: AppColors.textTertiary))
          : const Icon(Icons.chevron_right, color: AppColors.textTertiary),
    );
  }

  Widget _buildRiskSelector() {
    String riskDesc = '2.0% max risk per trade • Standard institutional growth';
    if (_selectedRisk == 'Low') {
      riskDesc = '1.0% max risk per trade • Conservative capital preservation';
    } else if (_selectedRisk == 'High') {
      riskDesc = '3.0% max risk per trade • Aggressive momentum allocation';
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.tune, color: AppColors.primary, size: 22),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Risk Level', style: TextStyle(color: AppColors.textPrimary, fontSize: 15)),
                    Text(riskDesc, style: const TextStyle(color: AppColors.textTertiary, fontSize: 12)),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: ['Low', 'Medium', 'High'].map((level) {
              final isSelected = _selectedRisk == level;
              final color = level == 'Low'
                  ? AppColors.success
                  : level == 'Medium'
                      ? AppColors.warning
                      : AppColors.error;
              return Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 3),
                  child: GestureDetector(
                    onTap: () {
                      setState(() => _selectedRisk = level);
                      _updateSetting('settings_selected_risk', level);
                      final pct = level == 'Low' ? '1%' : level == 'Medium' ? '2%' : '3%';
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text('🛡️ Risk level adjusted to $level ($pct account risk per trade)'),
                          duration: const Duration(seconds: 2),
                          behavior: SnackBarBehavior.floating,
                        ),
                      );
                    },
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      decoration: BoxDecoration(
                        color: isSelected ? color.withValues(alpha: 0.2) : AppColors.surfaceLight,
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(
                          color: isSelected ? color : Colors.transparent,
                        ),
                      ),
                      child: Text(
                        level,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: isSelected ? color : AppColors.textSecondary,
                          fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                          fontSize: 13,
                        ),
                      ),
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildDivider() {
    return const Divider(height: 1, indent: 56, color: AppColors.surfaceLight);
  }
}
