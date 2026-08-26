import 'package:flutter/foundation.dart';
import 'package:cached_network_image/cached_network_image.dart';

class ImageCacheService {
  static final ImageCacheService _instance = ImageCacheService._internal();
  factory ImageCacheService() => _instance;
  ImageCacheService._internal();

  Future<void> init() async {
    // Configure default image cache settings
    await Future.wait([
      // Configure cache size
      _configureCacheSize(),
      // Clear old cache
      _clearOldCache(),
    ]);
    
    debugPrint('Image cache service initialized');
  }

  Future<void> _configureCacheSize() async {
    // Set maximum cache size to 100 MB
    await DefaultCacheManager().emptyCache();
    await DefaultCacheManager().setMaximumCacheSize(100 * 1024 * 1024);
    await DefaultCacheManager().setMaximumCacheObjects(200);
    
    debugPrint('Image cache configured: 100MB max, 200 objects');
  }

  Future<void> _clearOldCache() async {
    // Clear images older than 7 days
    await DefaultCacheManager().removeOldFiles();
    debugPrint('Old cache files cleared');
  }

  Future<void> clearCache() async {
    await DefaultCacheManager().emptyCache();
    debugPrint('Image cache cleared');
  }

  Future<int> getCacheSize() async {
    // Return cache size in bytes
    return await DefaultCacheManager().getCacheSize();
  }
}