import re

path = r'c:\Users\ACER\Documents\SCHOOL WORKS\Falcon\mobile\lib\services\api\api_service.dart'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

header_split = text.split('static const int timeoutSeconds = 10;')
header = header_split[0] + 'static const int timeoutSeconds = 10;\n'
rest = header_split[1]

get_method = """
  Future<T> _get<T>(String endpoint, T Function(Map<String, dynamic>) fromJson) async {
    final url = '$baseUrl$endpoint';
    print("Calling: $url");
    try {
      final response = await http
          .get(Uri.parse(url))
          .timeout(const Duration(seconds: timeoutSeconds));

      print("Status Code: ${response.statusCode}");
      if (response.body.length > 500) {
        print("Response: ${response.body.substring(0, 500)}... [truncated]");
      } else {
        print("Response: ${response.body}");
      }

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return fromJson(data as Map<String, dynamic>);
      } else {
        throw Exception('Server error: ${response.statusCode} - ${response.reasonPhrase} for $url');
      }
    } on http.ClientException catch (e) {
      print("ClientException ($url): $e");
      throw Exception('Network connection failed. Please check your connection to the server.');
    } on TimeoutException catch (e) {
      print("TimeoutException ($url): $e");
      throw Exception('Request timed out after $timeoutSeconds seconds. Server is unreachable.');
    } on FormatException catch (e) {
      print("FormatException ($url): $e");
      throw Exception('Invalid data received from server.');
    } catch (e) {
      print("Unexpected Error ($url): $e");
      throw Exception('An unexpected error occurred: $e');
    }
  }

  Future<List<T>> _getList<T>(String endpoint, T Function(Map<String, dynamic>) fromJson) async {
    final url = '$baseUrl$endpoint';
    print("Calling: $url");
    try {
      final response = await http
          .get(Uri.parse(url))
          .timeout(const Duration(seconds: timeoutSeconds));

      print("Status Code: ${response.statusCode}");
      if (response.body.length > 500) {
        print("Response: ${response.body.substring(0, 500)}... [truncated]");
      } else {
        print("Response: ${response.body}");
      }

      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        return data.map((e) => fromJson(e as Map<String, dynamic>)).toList();
      } else {
        throw Exception('Server error: ${response.statusCode} - ${response.reasonPhrase} for $url');
      }
    } on http.ClientException catch (e) {
      print("ClientException ($url): $e");
      throw Exception('Network connection failed. Please check your connection to the server.');
    } on TimeoutException catch (e) {
      print("TimeoutException ($url): $e");
      throw Exception('Request timed out after $timeoutSeconds seconds. Server is unreachable.');
    } on FormatException catch (e) {
      print("FormatException ($url): $e");
      throw Exception('Invalid data received from server.');
    } catch (e) {
      print("Unexpected Error ($url): $e");
      throw Exception('An unexpected error occurred: $e');
    }
  }
"""

# The methods we want to replace all follow the pattern:
# Future<T> name(args) async {
#   ...
#   }
# } 
# Let's write a simple parser instead of regex because regex fails on nested braces.

def extract_methods(src):
    methods = []
    lines = src.split('\n')
    current_method = []
    in_method = False
    brace_count = 0
    
    i = 0
    while i < len(lines):
        line = lines[i]
        if 'Future<' in line and ') async {' in line and ' _get' not in line and ' _getList' not in line:
            in_method = True
            brace_count = line.count('{') - line.count('}')
            current_method.append(line)
        elif in_method:
            brace_count += line.count('{') - line.count('}')
            current_method.append(line)
            if brace_count == 0:
                methods.append('\n'.join(current_method))
                current_method = []
                in_method = False
        i += 1
    return methods

methods = extract_methods(rest)
refactored_rest = rest

for m in methods:
    # parse the method header
    header_match = re.search(r'Future<([^>]+)>\s+([a-zA-Z0-9_]+)\((.*?)\)\s+async\s+\{', m)
    if not header_match: continue
    
    return_type = header_match.group(1).strip()
    method_name = header_match.group(2).strip()
    args = header_match.group(3).strip()
    
    # parse endpoint from $baseUrl/endpoint
    endpoint_match = re.search(r'(?:baseUrl/|\$baseUrl)(.*?)(?:\'|\"|;)', m)
    if not endpoint_match: continue
    endpoint = endpoint_match.group(1).strip()
    # ensure it starts with /
    if not endpoint.startswith('/'):
        endpoint = '/' + endpoint
    
    # parse model_class from return ModelClass.fromJson
    # this might be a list map, or simple fromJson
    model_match = re.search(r'return ([A-Za-z0-9_]+)\.fromJson', m)
    model_class = model_match.group(1).strip() if model_match else "dynamic"
    
    if method_name == 'getWatchlist':
        replacement = """
  Future<List<MarketQuote>> getWatchlist({List<String>? symbols}) async {
    final query = symbols != null && symbols.isNotEmpty ? '?symbols=${symbols.join(',')}' : '';
    return _getList<MarketQuote>('/market-quotes/watchlist$query', MarketQuote.fromJson);
  }"""
    elif method_name == 'getMissionArtifacts':
        replacement = """
  Future<Map<String, dynamic>> getMissionArtifacts(String missionId) async {
    return _get<Map<String, dynamic>>('/missions/$missionId/artifacts', (data) => data);
  }"""
    elif args and 'symbol' in args and 'String' in args:
        replacement = f"""
  Future<{return_type}> {method_name}({args}) async {{
    return _get<{return_type}>('{endpoint}$symbol', {model_class}.fromJson);
  }}"""
    elif args and 'id' in args and 'String' in args:
        replacement = f"""
  Future<{return_type}> {method_name}({args}) async {{
    return _get<{return_type}>('{endpoint}$id', {model_class}.fromJson);
  }}"""
    else:
        replacement = f"""
  Future<{return_type}> {method_name}({args}) async {{
    return _get<{return_type}>('{endpoint}', {model_class}.fromJson);
  }}"""
        
    refactored_rest = refactored_rest.replace(m, replacement)

with open(path, 'w', encoding='utf-8') as f:
    f.write(header + get_method + refactored_rest)

print("Done refactoring directly to the file.")
