import datetime, configparser, json, requests, socket, time
from dateutil import parser
from tqdm import tqdm

def get_account_details(accountID, key):

    account_api_url = 'https://api.octopus.energy/v1/accounts/' + accountID
    account = requests.get(account_api_url, auth = (key,''))
    property = account.json()

    return {
            'electricity': {
                'meter': property['properties'][0]['electricity_meter_points'][0]['mpan'],
                'serial': property['properties'][0]['electricity_meter_points'][0]['meters'][0]['serial_number'],
                'tarrifs': property['properties'][0]['electricity_meter_points'][0]['agreements']
                },
            'gas': {
                'meter': property['properties'][0]['gas_meter_points'][0]['mprn'],
                'serial': property['properties'][0]['gas_meter_points'][0]['meters'][0]['serial_number'],
                'tarrifs': property['properties'][0]['gas_meter_points'][0]['agreements']
            }
    }


if __name__=="__main__":


    config = configparser.ConfigParser()
    config.read('config.ini')
    api_key = config['account']['api_key']

    account_details = get_account_details(config['account']['number'],api_key)
    days_to_import = int(config['import']['days'])

    carbon_server = config['carbon']['server']
    carbon_port = int(config['carbon']['port'])

    # 150 days seems to be the furthest back I can go. havent yet located how much should be available from the API.
     
    import_start_date = datetime.datetime.now() - datetime.timedelta(days=days_to_import)
    end_date = datetime.datetime.now() 
    delta = datetime.timedelta(days=1)
    last_successful_date = 'never'


    # Open the connection to the carbon server
    sock = socket.socket()
    sock.connect((carbon_server, carbon_port))

    print("\nImporting consumption data for account: %s" % config['account']['number'], end="\n\n")

    for i in tqdm (range (days_to_import ), desc="Loading consumption data..."):
        # Import the data for a single day - lazy as I dont need to deal with pagination. Optimisations will come later 
        params = {'order_by': 'period', 'period_from': import_start_date.strftime("%Y-%m-%dT%H:%M:00Z"), 'period_to': import_start_date.strftime("%Y-%m-%dT23:59:00Z") }
        for fuel in {'gas','electricity'}:
            api_url = 'https://api.octopus.energy/v1/%s-meter-points/%s/meters/%s/consumption' % (fuel, account_details[fuel]['meter'], account_details[fuel]['serial'] )

            response = requests.get(api_url, params = params, auth = (api_key,''))
            response_results = response.json()

            if response_results['count'] != 0:
                for result in response_results['results']:
                    epoch = datetime.datetime.timestamp(parser.parse(result['interval_start'])) 
                    value = result['consumption']
            
                    message = 'octopus.%s.consumption %s %d\n' % (fuel, value, epoch)
                    try:
                        sock.sendto(message.encode('utf-8'), (carbon_server, carbon_port))
                    except:
                        print('Send to Carbon failed')
                    last_successful_date = import_start_date.strftime("%Y-%m-%d")
            
            import_start_date += delta

    # Close the connection to the carbon server
    sock.close()
   
    print('\nImported data to at least: %s \n' % last_successful_date)
