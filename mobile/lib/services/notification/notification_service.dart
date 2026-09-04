import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import '../../models/signal.dart';

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  final FlutterLocalNotificationsPlugin _notificationsPlugin =
      FlutterLocalNotificationsPlugin();
  bool _initialized = false;

  static const String signalChannelId = 'falcon_signals';
  static const String signalChannelName = 'Falcon Trade Signals';
  static const String signalChannelDesc =
      'Real-time trading signal alerts with Entry, SL, and TP from Falcon AI';

  Future<void> init() async {
    if (_initialized) return;

    const AndroidInitializationSettings androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');

    const DarwinInitializationSettings iosSettings =
        DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );

    const InitializationSettings initSettings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );

    try {
      await _notificationsPlugin.initialize(
        initSettings,
        onDidReceiveNotificationResponse: (NotificationResponse response) {
          debugPrint('Notification tapped with payload: ${response.payload}');
        },
      );

      // Create Android Notification Channel with maximum priority
      final AndroidFlutterLocalNotificationsPlugin? androidImplementation =
          _notificationsPlugin.resolvePlatformSpecificImplementation<
              AndroidFlutterLocalNotificationsPlugin>();

      if (androidImplementation != null) {
        await androidImplementation.createNotificationChannel(
          const AndroidNotificationChannel(
            signalChannelId,
            signalChannelName,
            description: signalChannelDesc,
            importance: Importance.max,
            playSound: true,
            enableVibration: true,
            showBadge: true,
          ),
        );

        // Request runtime permission for Android 13+
        await androidImplementation.requestNotificationsPermission();
      }

      _initialized = true;
      debugPrint('[NotificationService] Initialized successfully');
    } catch (e) {
      debugPrint('[NotificationService] Initialization error: $e');
    }
  }

  Future<void> showSignalNotification({
    required int id,
    required String title,
    required String body,
    String? payload,
  }) async {
    if (!_initialized) {
      await init();
    }

    const AndroidNotificationDetails androidDetails =
        AndroidNotificationDetails(
      signalChannelId,
      signalChannelName,
      channelDescription: signalChannelDesc,
      importance: Importance.max,
      priority: Priority.high,
      ticker: 'Falcon Trade Signal',
      playSound: true,
      enableVibration: true,
      styleInformation: BigTextStyleInformation(''),
    );

    const DarwinNotificationDetails iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
    );

    const NotificationDetails platformDetails = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );

    try {
      await _notificationsPlugin.show(
        id,
        title,
        body,
        platformDetails,
        payload: payload,
      );
      debugPrint('[NotificationService] Showed notification #$id: $title');
    } catch (e) {
      debugPrint('[NotificationService] Failed to show notification: $e');
    }
  }

  Future<void> showTradeAlert(Signal signal) async {
    final isBuy = signal.action.toUpperCase() == 'BUY';
    final emoji = isBuy ? '🟢 BUY' : '🔴 SELL';
    final title = '🦅 FALCON SIGNAL: ${signal.symbol} $emoji';
    final body =
        'Entry: ${signal.entry} | SL: ${signal.stopLoss} | TP: ${signal.takeProfit}\n'
        'Confidence: ${signal.confidence}% (${signal.timeframe})';

    await showSignalNotification(
      id: signal.id,
      title: title,
      body: body,
      payload: '/signals',
    );
  }
}
