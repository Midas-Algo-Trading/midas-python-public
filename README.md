# Midas (python)
This program allows users to add strategies that can use stock data retrieved from an API to create and send real stock orders to TD Ameritrade (stock broker).   
*Git history has been removed. See [Notes](#Notes)*

### Some cool features
* Can run trade autonomously without any human intervention
* Supports long & short orders
* Scrapes data to track if a company is scheduled to have a stock split. If so, it will immediately close all positions for that stock
* Sends alert texts when something goes wrong
* Autonomously stops trading strategies when they lose more than 2%
* Safety mechanisms to reduce the chance of incorrect orders being sent to TD Ameritrade.

### Notes
- I had to remove parts of the git history as some commits contained sensitive information, so I created a new repo and cleared the git history.
- This was my most complex and likely largest python project.
- A bit more than a year ago, the person I work with and I decided to switch to C++ as it is a more performant language and is meant for larger-scale projects
- We still occasionally push to the repo to fix bugs, but as we do not plan to use this project for much longer, I have pushed very quick and ugly code to fix bugs
  - Over time this has resulted in the code base becoming much less clean
