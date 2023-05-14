# Tronity Integration for Home Assistant

The Tronity Integration is a custom integration developed for Home Assistant, designed to enable you to monitor and 
utilize the data provided by Tronity. By integrating Tronity with Home Assistant, you can easily monitor your vehicle's 
data and create automations based on it.

## Installation

#### HACS Installation Way
1. Open HACS
2. Select Integrations, then select the 3-dots in the upper-right corner, then select Custom Repositories.
3. Put the Reposity URL in the Repository field, then select Integration in the Category dropdown list and click Add.
4. Now you can search for Tronity in HACS and install it
5. After install you need to rebstart Home Assistent
6. Now you can skip Configuration and proceed with Usage

#### Normalway
1. Download or clone the Tronity Integration to your local machine.
2. Navigate to the custom_components directory in your Home Assistant installation directory.
3. Create a new directory called tronity.
4. Copy the files from the downloaded Tronity Integration to the tronity directory.
5. Restart Home Assistant.

## Configuration

1. Open your configuration.yaml file in your Home Assistant installation directory.
2. Add the following code to the file: </br>
  ```tronity:```
3. Save the configuration file.
4. Restart Home Assistant.

## Usage

1. Navigate to the Setting section and click on Devices & Services.
2. Click on the Add Integration button.
3. Search for Tronity and select it.
4. In order to complete the integration setup, you will need to provide your Tronity client ID, Client Secret, and Vehicle ID. You can find this information on the Tronity Platform website: https://app.tronity.tech/.
5. Once the integration is set up, you can add Tronity sensors to your Home Assistant dashboard to monitor your vehicle's data.

### Setting up multiple vehicles
To monitor data for multiple vehicles, you can set up multiple instances of Tronity in Home Assistant. Follow the same steps as above for each vehicle you want to monitor. Once you have set up the integrations for all your vehicles, you can add the corresponding Tronity sensors to your dashboard to view the data for each vehicle.

### How to implement the Tronity example_dashboard YAML file
1. Navigate to the Setting section and click on Dashboards.
2. Click on the Add Dashboard.
4. Select your newly created Dashboard.
3. Press the three dots on the top right, click on Edit Dashboard and select "Start with an empty dashboard". 
4. Click the Add Card button and select "Manual Card" from the list of card types and paste the example_dashboard YAML file into the card's configuration text box.
5. Customize the configuration for your specific sensors by following the comments in the YAML file.
6. Optionally, replace the friendly names and icons in the YAML file with your own preferences.
7. Click Save to save the changes to the dashboard.

## Contributing

If you would like to contribute to this custom integration, feel free to submit a pull request with your changes.

## Feedback

If you encounter any issues or have any feedback on this custom integration, please raise an issue on the GitHub repository for this integration.


