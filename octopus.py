import datetime, configparser, json, requests, socket, time
from dateutil import parser

config_file = 'config.ini'
config = configparser.ConfigParser()
config.read(config_file)

api_key = config['api']['api_key']

carbon_server = config['carbon']['server']
carbon_port = int(config['carbon']['port'])

import_start_date = datetime.datetime.now() - datetime.timedelta(days=180)
end_date = datetime.datetime.now() 
delta = datetime.timedelta(days=1)
last_successful_date = 'never'

# Open the connection to the carbon server
sock = socket.socket()
sock.connect((carbon_server, carbon_port))

while (import_start_date <= end_date):
    # Import the data for a single day
    params = {'order_by': 'period', 'period_from': import_start_date.strftime("%Y-%m-%dT%H:%M:00Z"), 'period_to': import_start_date.strftime("%Y-%m-%dT23:59:00Z") }
   
    
    for fuel in {'gas','electricity'}:
        api_url = config['api']['api_url'] + '/%s-meter-points/%s/meters/%s/consumption' % (fuel, config[fuel]['meter'],config[fuel]['serial_no'] )

        response = requests.get(api_url, params = params, auth = (api_key,''))
        response_results = response.json()

        if response_results['count'] != 0:
            print('Uploading %s data for: %s' %  (fuel, import_start_date.strftime("%Y-%m-%d")) )
            for result in response_results['results']:
                epoch = datetime.datetime.timestamp(parser.parse(result['interval_start'])) 
                value = result['consumption']
        
                message = 'octopus.%s.consumption %s %d\n' % (fuel, value, epoch)
                try:
                    sock.sendto(message.encode('utf-8'), (carbon_server, carbon_port))
                except:
                    # what to do if the send fails?
                    print('Send to Carbon failed')
                last_successful_date = import_start_date.strftime("%Y-%m-%d")
        else:
            print('Skipping: %s as no data available' % import_start_date.strftime("%Y-%m-%d") )

    import_start_date += delta

# Close the connection to the carbon server
sock.close()
print('Imported data to at least: %s' % last_successful_date)
