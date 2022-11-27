import datetime, configparser, json, requests, socket, time, logging
from datetime import timezone
from dateutil import parser
from tqdm import tqdm

def get_account_details(accountID, key):
    print('\n\nImporting account details :', accountID, '\n')

    account_api_url = 'https://api.octopus.energy/v1/accounts/' + accountID
    account = requests.get(account_api_url, auth = (key,''))
    property = account.json()


    return {
            'electricity': {
                'meter': property['properties'][0]['electricity_meter_points'][0]['mpan'],
                'serial': property['properties'][0]['electricity_meter_points'][0]['meters'][0]['serial_number'],
                'tariffs': property['properties'][0]['electricity_meter_points'][0]['agreements']
                },
            'gas': {
                'meter': property['properties'][0]['gas_meter_points'][0]['mprn'],
                'serial': property['properties'][0]['gas_meter_points'][0]['meters'][0]['serial_number'],
                'tariffs': property['properties'][0]['gas_meter_points'][0]['agreements']
            }
    }

def retrieve_rates(api_key, accountID, account_details):
    
    print('Retrieving tariffs...')
    tariffs = []
    for fuel in {'gas','electricity'}:
        # retrieve all applicable tariffs and get product rates
        for tariff in account_details[fuel]['tariffs']:

            tariff_code=tariff['tariff_code']

            tariff_from = standardise_date(tariff['valid_from'])
            tariff_to = standardise_date(tariff['valid_to'])
           
            product_code=tariff_code.removesuffix('-E')[5:]
            print('From: %s  To: %s in UTC: %s' %(tariff_from, tariff_to, 'x'))


def standardise_date(date):
    result = date
    if date is None:
        result = datetime.datetime.utcnow()

    return result

def get_current_tariff(api_key, account_details, fuel, epoch):
    for tariff in account_details[fuel]['tariffs']:

        tariff_from = parser.parse(standardise_date(tariff['valid_from']))
        tariff_to = parser.parse(standardise_date(tariff['valid_to']))

        if  (epoch >= tariff_from.timestamp() ) and (epoch <= tariff_to.timestamp()):
            tariff_code = tariff['tariff_code']

    # Strip first 5 chars (e.g. G-1R-) and remove any trailing -E to get the product code.
    product_code=tariff_code.removesuffix('-E')[5:]

    account_api_url = 'https://api.octopus.energy/v1/products/' + product_code
    response = requests.get(account_api_url, auth = (api_key,''))
    product = response.json()

    # for GO electricity product, standard_unit_rates show the day / night rates NOT the /(day or night)-unit-rates/ APIs
    # https://api.octopus.energy/v1/products/%s/%s-tariffs/%s/standard-unit-rates/ % (product_code, fuel, tariff-code)
    # https://api.octopus.energy/v1/products/%s/%s-tariffs/%s/standing-charges/ % (product_code, fuel, tariff-code)

    return product_code

if __name__=="__main__":

    config = configparser.ConfigParser()
    config.read('config.ini')

    api_key = config['account']['api_key']
    api_url = config['account']['api_url']
    account_no = config['account']['number']

    logging.basicConfig(filename=config['logger']['log_file'], encoding='utf-8', level=logging.INFO)

    account_details = get_account_details(account_no,api_key)
    

    # rates = retrieve_rates(account_no, api_key, account_details)

    days_to_import = int(config['import']['days'])

    carbon_server = config['carbon']['server']
    carbon_port = int(config['carbon']['port'])

    # 150 days seems to be the furthest back I can go. havent yet located how much should be available from the API.
     
    import_start_date = datetime.datetime.now() - datetime.timedelta(days=days_to_import)
    end_date = datetime.datetime.now() 
    delta = datetime.timedelta(days=1)
    last_successful_date = 'never'

    # Open the connection to the carbon server
    carbon = socket.socket()
    try:
        carbon.connect((carbon_server, carbon_port))
    except:
        print('\nUnable to connect to the Carbon server at: %s port %s' % (carbon_server, carbon_port))
        exit()

    for i in tqdm (range (days_to_import ), desc="Loading consumption data..."):
        # Import the data for a single day - lazy as I dont need to deal with pagination. Optimisations will come later 
        params = {'order_by': 'period', 'period_from': import_start_date.strftime("%Y-%m-%dT00:00:00Z"), 'period_to': import_start_date.strftime("%Y-%m-%dT23:59:00Z") }
        for fuel in {'gas','electricity'}:
            api_url = 'https://api.octopus.energy/v1/%s-meter-points/%s/meters/%s/consumption' % (fuel, account_details[fuel]['meter'], account_details[fuel]['serial'] )

            response = requests.get(api_url, params = params, auth = (api_key,''))
            response_results = response.json()

            if response_results['count'] != 0:

                logging.info((import_start_date.strftime("%Y-%m-%dT00:00:00Z"), import_start_date.strftime("%Y-%m-%dT23:59:00Z"), response_results['count']))
                
                for result in response_results['results']:
                    
                    current_interval = parser.parse(result['interval_start'])

                    epoch = datetime.datetime.timestamp(current_interval) 
                    value = result['consumption']

                    #x = get_current_tariff(api_key, account_details, epoch, fuel, epoch)

                    message = 'octopus.%s.consumption %s %d\n' % (fuel, value, epoch)
                    try:
                        carbon.send(message.encode('utf-8'))
                        last_successful_date = import_start_date.strftime("%Y-%m-%d")
                    except:
                        print('Send to Carbon failed')
            
        import_start_date += delta

    # Close the connection to the carbon server
    carbon.close()

    print('\nImported data to: %s \n' % last_successful_date)
