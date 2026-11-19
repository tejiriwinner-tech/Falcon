class PriceFormatter {
  PriceFormatter._();

  static int decimalsFor(String symbol) {
    final s = symbol.toUpperCase();
    if (s.contains('XAU') ||
        s.contains('GOLD') ||
        s.contains('NAS') ||
        s.contains('US30') ||
        s.contains('SPX') ||
        s.contains('US500') ||
        s.contains('USTEC') ||
        s.contains('GER40') ||
        s.contains('UK100') ||
        s.contains('BTC') ||
        s.contains('ETH')) {
      return 2;
    }
    if (s.contains('JPY') || s.contains('XAG')) {
      return 3;
    }
    return 5;
  }

  static String format(String symbol, double price) {
    return price.toStringAsFixed(decimalsFor(symbol));
  }

  static double pipSize(String symbol) {
    final s = symbol.toUpperCase();
    if (s.contains('JPY') || s.contains('XAG')) {
      return 0.01;
    }
    if (s.contains('XAU') || s.contains('GOLD')) {
      return 0.10;
    }
    if (s.contains('NAS') ||
        s.contains('US30') ||
        s.contains('SPX') ||
        s.contains('US500') ||
        s.contains('USTEC') ||
        s.contains('GER40') ||
        s.contains('UK100') ||
        s.contains('BTC') ||
        s.contains('ETH')) {
      return 1.0;
    }
    return 0.0001;
  }
}
