# Octopus Energy Data Dashboard

Small project to pull consumption data out of Ocotopus Energy's API utilissing a python script which then uploads into a Graphite Time Series DB, which is then consumed by Graphana for visualisations. 

![High Level Architecture](https://raw.githubusercontent.com/hissing-sid/octopus_energy/main/images/octopus_dashboard.png)

Dashboarding is being done utilising Grafana reading the data out of the Graphite time series database.
![Example Dashboard](https://raw.githubusercontent.com/hissing-sid/octopus_energy/main/images/grafana.png)