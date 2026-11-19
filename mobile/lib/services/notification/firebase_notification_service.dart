import 'dart:async';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'notification_service.dart';

@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  // Ensure Firebase is initialized for background isolate
  try {
    await Firebase.initializeApp();
  } catch (e) {
    debugPrint('[FCM Background] Firebase init error: $e');
  }
  debugPrint('[FCM Background] Handling message: ${message.messageId} - ${message.notification?.title}');
}

class FirebaseNotificationService {
  static final FirebaseNotificationService _instance =
      FirebaseNotificationService._internal();
  factory FirebaseNotificationService() => _instance;
  FirebaseNotificationService._internal();

  bool _initialized = false;
  static const String signalTopic = 'falcon_signals';

  Future<void> init() async {
    if (_initialized) return;

    try {
      await Firebase.initializeApp();

      // Register background handler
      FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

      // Request permissions
      final messaging = FirebaseMessaging.instance;
      final settings = await messaging.requestPermission(
        alert: true,
        announcement: false,
        badge: true,
        carPlay: false,
        criticalAlert: true,
        provisional: false,
        sound: true,
      );

      debugPrint('[FirebaseNotificationService] Permission status: ${settings.authorizationStatus}');

      // Enable foreground display
      await messaging.setForegroundNotificationPresentationOptions(
        alert: true,
        badge: true,
        sound: true,
      );

      // Subscribe to signal broadcasts (not supported on web)
      if (!kIsWeb) {
        try {
          await messaging.subscribeToTopic(signalTopic);
          debugPrint('[FirebaseNotificationService] Subscribed to topic: $signalTopic');
        } catch (e) {
          debugPrint('[FirebaseNotificationService] Topic subscription skipped: $e');
        }
      }

      // Get FCM token for debugging / target alerts
      try {
        final token = await messaging.getToken();
        debugPrint('[FirebaseNotificationService] FCM Token: $token');
      } catch (e) {
        debugPrint('[FirebaseNotificationService] Token retrieval error: $e');
      }

      // Foreground message listener: surface via local notification banner
      FirebaseMessaging.onMessage.listen((RemoteMessage message) {
        debugPrint('[FirebaseNotificationService] Foreground message received: ${message.notification?.title}');
        final notification = message.notification;
        if (notification != null) {
          NotificationService().showSignalNotification(
            id: DateTime.now().millisecondsSinceEpoch ~/ 1000,
            title: notification.title ?? 'Falcon Trade Alert',
            body: notification.body ?? '',
            payload: message.data['signal_id']?.toString(),
          );
        }
      });

      // App opened from notification
      FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
        debugPrint('[FirebaseNotificationService] App opened from notification: ${message.data}');
      });

      // Check if launched by notification from terminated state
      final initialMessage = await messaging.getInitialMessage();
      if (initialMessage != null) {
        debugPrint('[FirebaseNotificationService] Launched from terminated notification: ${initialMessage.data}');
      }

      _initialized = true;
      debugPrint('[FirebaseNotificationService] Initialized successfully');
    } catch (e, stackTrace) {
      debugPrint('[FirebaseNotificationService] Initialization error: $e\n$stackTrace');
    }
  }
}
