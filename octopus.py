# import datetime module
import datetime, configparser, json, requests, socket, time
from dateutil import parser

config_file = 'octopus.ini'
config = configparser.ConfigParser()
config.read(config_file)

api_key = config['octopus']['api_key']
mpan=config['electricity']['mpan']
serial_no=config['electricity']['serial_no']

carbon_server = config['carbon']['server']
carbon_port = int(config['carbon']['port'])

import_start_date = datetime.datetime.strptime(config['last_import']['date'], "%Y-%m-%d")
end_date = datetime.datetime.now()
delta = datetime.timedelta(days=1)
last_successful_date = 'never'

while (import_start_date <= end_date):
    # Import the data for a single day
    params = {'order_by': 'period', 'period_from': import_start_date.strftime("%Y-%m-%dT%H:%M:00Z"), 'period_to': import_start_date.strftime("%Y-%m-%dT23:59:00Z") }
       
    for fuel in {'gas','electricity'}:
        api_url = config['octopus']['api_url'] + '/%s-meter-points/%s/meters/%s/consumption' % (fuel, config[fuel]['meter'],config[fuel]['serial_no'] )

        response = requests.get(api_url, params = params, auth = (api_key,''))
        response_results = response.json()

        if response_results['count'] != 0:
            print('Uploading %s data for: %s' %  (fuel, import_start_date.strftime("%Y-%m-%d")) )
            for result in response_results['results']:
                epoch= datetime.datetime.timestamp(parser.parse(result['interval_start'])) 
                value = result['consumption']
        
                message = 'octopus.%s.consumption %s %d\n' % (fuel, value, epoch)

                sock = socket.socket()
                sock.connect((carbon_server, carbon_port))
                sock.sendto(message.encode('utf-8'), (carbon_server, carbon_port))
                sock.close()
            
                last_successful_date = import_start_date.strftime("%Y-%m-%d")
        else:
            print('Skipping: %s as no data available' % import_start_date.strftime("%Y-%m-%d") )

    import_start_date += delta

print('Imported data to: %s' % last_successful_date)

# Write out last successful import to config file, to ensure we can incrementally load  next run.
config["last_import"].update({"date":last_successful_date} )
with open(config_file,"w") as file_object:
    config.write(file_object)