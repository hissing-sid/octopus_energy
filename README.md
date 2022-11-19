# Octopus Energy Data Dashboard

Small project to pull consumption data out of Octopus Energy's API utilissing a python script which then uploads into a Graphite Time Series DB, which is then consumed by Graphana for visualisations. 

I will start with a caveat; I am not a Python programmer so I am no expecting the code to be good, nice, clean, thorough but functional. If you feel like offering comments that can help improve things, then great! Even better commit your ideas to the repo.

My reference for the API has been the excellent guide published by Guy Lipman which can be found here: https://www.guylipman.com/octopus/api_guide.html



![High Level Architecture](https://raw.githubusercontent.com/hissing-sid/octopus_energy/main/images/octopus_dashboard.png)

Dashboarding is being done utilising Grafana reading the data out of the Graphite.
![Example Dashboard](https://raw.githubusercontent.com/hissing-sid/octopus_energy/main/images/grafana.png)