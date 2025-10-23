from src.fyers_api_utils import get_fyers_client

def test_option_symbols():
    client = get_fyers_client()
    if not client:
        print("Failed to get Fyers client")
        return
    
    # Test with actual strikes that might exist
    symbols_to_test = [
        'NSE:NIFTY25OCT1625250CE',
        'NSE:NIFTY25OCT1625300CE', 
        'NSE:NIFTY25OCT1625350CE',
        'NSE:BANKNIFTY25OCT1656400CE',
        'NSE:BANKNIFTY25OCT1656500CE',
        'NSE:BANKNIFTY25OCT1656600CE',
        'NSE:NIFTY50-INDEX'  # This should work as reference
    ]
    
    for symbol in symbols_to_test:
        try:
            response = client.quotes(data={'symbols': symbol})
            if response.get('s') == 'ok':
                print(f'✅ Valid format: {symbol}')
                if 'v' in response.get('d', [{}])[0]:
                    ltp = response['d'][0]['v'].get('ltp', 'N/A')
                    print(f'   LTP: {ltp}')
            else:
                print(f'❌ Invalid: {symbol} - {response.get("message", "Unknown error")}')
        except Exception as e:
            print(f'❌ Error: {symbol} - {e}')

if __name__ == '__main__':
    test_option_symbols()