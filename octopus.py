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
                'tariffs': property['properties'][0]['electricity_meter_points'][0]['agreements']
                },
            'gas': {
                'meter': property['properties'][0]['gas_meter_points'][0]['mprn'],
                'serial': property['properties'][0]['gas_meter_points'][0]['meters'][0]['serial_number'],
                'tariffs': property['properties'][0]['gas_meter_points'][0]['agreements']
            }
    }

def retrieve_rates(api_key, accountID, account_details):
    for fuel in {'gas','electricity'}:
        # retrieve all applicable tariffs and get product rates
        for tariff in account_details[fuel]['tariffs']:
            tariff_code=tariff['tariff_code']
            tariff_from = normalise_date(tariff['valid_from'])
            tariff_to = normalise_date(tariff['valid_to'])

            
            
            product_code=tariff_code.removesuffix('-E')[5:]
            

    exit()

def normalise_date(date):
    if date is None:
        print('None')
        result = datetime.datetime.now()
    elif "00Z" in date:
        print('Z')
        result =  datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M:00Z")
    elif "+" in date:
        print('No Z')
        # result = datetime.datetime.strptime(date.replace('+01:00', 'Z'), "%Y-%m-%dT%H:%M:00Z" ) + datetime.timedelta(hours=1)
        result = datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M:00%z" ) 

    print(date, '=>', result)
    return result

def convert_to_epoch(date):
    if date is None:
        epoch = datetime.datetime.now().timestamp()
    elif "00Z" in date:
        epoch =  datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M:00Z").timestamp()
    else:
        date_adjusted = datetime.datetime.strptime(date.replace('+01:00', 'Z'), "%Y-%m-%dT%H:%M:00Z" ) + datetime.timedelta(hours=1)
        epoch =  date_adjusted.timestamp()

    return epoch

def get_current_tariff(api_key, account_details, fuel, epoch):
    for tariff in account_details[fuel]['tariffs']:

        tariff_from = convert_to_epoch(tariff['valid_from'])
        tariff_to = convert_to_epoch(tariff['valid_to'])

        try:
            tariff_to = datetime.datetime.strptime(tariff['valid_to'], "%Y-%m-%dT%H:%M:00Z").timestamp()
        except:
            tariff_to = datetime.datetime.now().timestamp()

        if  (epoch >= tariff_from ) and (epoch <= tariff_to):
            tariff_code = tariff['tariff_code']

    # Strip first 5 chars (e.g. G-1R-) and remove any trailing -E to get the product code.
    product_code=tariff_code.removesuffix('-E')[5:]

    account_api_url = 'https://api.octopus.energy/v1/products/' + product_code
    response = requests.get(account_api_url, auth = (api_key,''))
    product = response.json()

    print('\nTariff Code:', tariff_code)
    print('Product:', product_code)
    print('Fuel:', fuel)
    print(product['description'])
    print('===========================================================================')
    print(product)
    exit()

    # for GO electricity product, standard_unit_rates show the day / night rates NOT the /(day or night)-unit-rates/ APIs
    # https://api.octopus.energy/v1/products/%s/%s-tariffs/%s/standard-unit-rates/ % (product_code, fuel, tariff-code)
    # https://api.octopus.energy/v1/products/%s/%s-tariffs/%s/standing-charges/ % (product_code, fuel, tariff-code)

    return product_code

if __name__=="__main__":


    config = configparser.ConfigParser()
    config.read('config.ini')
    api_key = config['account']['api_key']

    account_details = get_account_details(config['account']['number'],api_key)
    rates = retrieve_rates(config['account']['number'],api_key, account_details)



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

                    x = get_current_tariff(api_key, account_details, fuel, epoch)
            
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
