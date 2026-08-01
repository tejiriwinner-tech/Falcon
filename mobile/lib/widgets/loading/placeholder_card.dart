import 'package:flutter/material.dart';
import '../cards/app_card.dart';

class PlaceholderCard extends StatelessWidget {
  final double height;
  
  const PlaceholderCard({super.key, this.height = 100});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: SizedBox(
        height: height,
        child: const Center(
          child: CircularProgressIndicator(),
        ),
      ),
    );
  }
}
