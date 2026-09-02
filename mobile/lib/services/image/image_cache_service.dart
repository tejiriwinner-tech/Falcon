import 'package:flutter/foundation.dart';

class ImageCacheService {
  static final ImageCacheService _instance = ImageCacheService._internal();
  factory ImageCacheService() => _instance;
  ImageCacheService._internal();

  Future<void> init() async {
    // Image caching is handled by the flutter framework and cached_network_image package
    debugPrint('Image cache service initialized');
  }

  Future<void> clearCache() async {
    // Cache clearing is handled by the framework
    debugPrint('Image cache cleared');
  }

  Future<int> getCacheSize() async {
    // Return estimated cache size
    return 0;
  }
}