# CAPTAIN_BRIEFING_TRACE.md

## Widget Rendering Trace

### Mobile Widget Logic

#### File: `mobile/lib/screens/dashboard/dashboard_screen.dart`

#### Widget Conditional Rendering
```dart
// Line 89-99
if (dash?.decision == null) {
  print("[WIDGET DIAGNOSTIC] Showing PlaceholderCard because dash.decision is null");
  const PlaceholderCard(height: 220)
} else
  Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      _buildCaptainsBriefing(dash!.decision!),
      // ... other widgets
    ],
  )
```

#### Diagnostic Logs Added
```dart
print("[WIDGET DIAGNOSTIC] Dashboard loaded: ${dash != null}");
print("[WIDGET DIAGNOSTIC] Decision object: ${dash?.decision}");
if (dash?.decision != null) {
  print("[WIDGET DIAGNOSTIC] Greeting: ${dash!.decision!.greetingMessage}");
  print("[WIDGET DIAGNOSTIC] Confidence: ${dash.decision!.confidenceScore}");
}
```

#### Captain's Briefing Builder
```dart
Widget _buildCaptainsBriefing(DecisionEngineResponse data) {
  print("[CAPTAIN BRIEFING DIAGNOSTIC] _buildCaptainsBriefing called");
  print("[CAPTAIN BRIEFING DIAGNOSTIC] DecisionEngineResponse data: $data");
  print("[CAPTAIN BRIEFING DIAGNOSTIC] Greeting message: ${data.greetingMessage}");
  print("[CAPTAIN BRIEFING DIAGNOSTIC] Recommendation: ${data.recommendation}");
  print("[CAPTAIN BRIEFING DIAGNOSTIC] Confidence score: ${data.confidenceScore}");
  
  return GestureDetector(
    onTap: () => context.push('/decision-artifacts'),
    child: Column(
      children: [
        _buildGreetingHeader(data),
        _buildStrategyContextCard(data),
        _buildBadgesRow(data),
        _buildConfidenceGapCard(data),
        _buildConfidenceBreakdown(data),
        _buildDecisionChecklist(data),
        _buildCaptainsAction(data),
      ],
    ),
  );
}
```

### Execution Flow

#### Scenario 1: Decision is Null (Current State)
1. Dashboard loads data from API
2. `dash.decision` is `null`
3. Widget checks `dash?.decision == null`
4. **Result**: Shows `PlaceholderCard(height: 220)` ⚠️
5. **Diagnostic Output**: `[WIDGET DIAGNOSTIC] Showing PlaceholderCard because dash.decision is null`

#### Scenario 2: Decision is Not Null (Expected State)
1. Dashboard loads data from API
2. `dash.decision` contains `DecisionEngineResponse`
3. Widget checks `dash?.decision == null` → false
4. **Result**: Calls `_buildCaptainsBriefing(dash.decision!)` ✅
5. **Diagnostic Output**: 
   ```
   [CAPTAIN BRIEFING DIAGNOSTIC] _buildCaptainsBriefing called
   [CAPTAIN BRIEFING DIAGNOSTIC] Greeting message: Captain's Briefing: Operational parameters optimal.
   [CAPTAIN BRIEFING DIAGNOSTIC] Recommendation: BUY
   [CAPTAIN BRIEFING DIAGNOSTIC] Confidence score: 85.0
   ```

### Widget Components (When Decision Available)

#### 1. Greeting Header
- Captain icon (🦅)
- Time-based greeting ("Good morning/afternoon/evening, Captain.")
- Engine version display
- Captain's briefing message

#### 2. Strategy Context Card
- Strategy ID and name
- Strategy version
- Strategy score

#### 3. Badges Row
- Recommendation badge (BUY/SELL/WAIT)
- Status badge (READY/BLOCKED/WAIT)
- Trade quality badge (A/B/C)

#### 4. Confidence Gap Card
- Current confidence score
- Minimum confidence threshold (85)
- Confidence gap calculation

#### 5. Confidence Breakdown
- Technical signals contribution (35%)
- Market sentiment contribution (25%)
- News impact contribution (20%)
- Historical performance contribution (15%)
- Consistency bonus (5%)

#### 6. Decision Checklist
- Passed checks with green indicators
- Failed checks with red indicators
- Blocking conditions highlighted

#### 7. Missing Conditions (if any)
- List of blocking operational conditions
- Each condition with title and description

#### 8. Captain's Action
- Recommended action message
- Action urgency indicator
- Next steps guidance

### Current State Analysis

#### Widget State
- **Dashboard Loaded**: ✅ Yes
- **Decision Object**: ❌ Null
- **Widget Displayed**: ⚠️ PlaceholderCard
- **User Experience**: Loading spinner/placeholder

#### Expected Widget State
- **Dashboard Loaded**: ✅ Yes
- **Decision Object**: ✅ DecisionEngineResponse
- **Widget Displayed**: ✅ Captain's Briefing with full content
- **User Experience**: Complete decision information

### Mobile Parser Handling

#### File: `mobile/lib/models/dashboard.dart`
```dart
factory DashboardResponse.fromJson(Map<String, dynamic> j) {
  print("[MOBILE PARSING DIAGNOSTIC] 'decision' key exists: ${j.containsKey('decision')}");
  print("[MOBILE PARSING DIAGNOSTIC] 'decision' value: ${j['decision']}");
  
  if (j['decision'] != null) {
    print("[MOBILE PARSING DIAGNOSTIC] Decision JSON: ${j['decision']}");
    final decision = DecisionEngineResponse.fromJson(j['decision'] as Map<String, dynamic>);
    print("[MOBILE PARSING DIAGNOSTIC] Decision parsed successfully, greeting: ${decision.greetingMessage}");
  } else {
    print("[MOBILE PARSING DIAGNOSTIC] WARNING: 'decision' is null in JSON");
  }
  
  return DashboardResponse(
    // ... other fields
    decision: j['decision'] != null ? DecisionEngineResponse.fromJson(j['decision'] as Map<String, dynamic>) : null,
  );
}
```

### Conclusion

✅ **Widget rendering logic is working correctly**
- Widget properly handles null decision state
- Shows appropriate placeholder when no decision available
- Would render full Captain's Briefing when decision is present
- No rendering bugs or UI issues found

❌ **Decision data is missing from backend**
- Backend returns `"decision": null` in API response
- This is due to missing market_state data
- Not a widget or parsing issue

### Next Steps Required
To fix Captain's Briefing display, the backend must provide a non-null decision object by ensuring market_state data is available when the dashboard endpoint is called.