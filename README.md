# Wispar

Hello! Thank you for downloading our project, Wispar! This README goes over the deployment process, and will get you up and running!

## Preparing to Use Wispar

### Python
The first thing you need to do in order to run Wispar is have Python installed, as well as any of the dependent packages in deploy.py. In no particular order, you will need `dotenv`, `pathlib`, `getpass`, `re`, `string`, `secrets`, `subprocess`, and `os`. Most of these should already be installed, but some may need to be `pip install`'d as well.

### Docker
#### Download Docker
Wispar works as a series of Docker Containers on your machine, communicating in tandem to host, manage, and serve your books. Because of this, if you don not have Docker installed you will need to navigate to the [Docker download page](https://docs.docker.com/get-started/get-docker/), and choose the download that's right for your system.

#### Creating Docker Containers
Thanks to the simple deployment script `deploy.py`, the only thing you have to do once you've downloaded Docker is, in the root folder of the project, run the command `python deploy.py`. This will guide your through the process of creating a database password, an admin username/password, and configuring a few special settings. Once this is done, an `.env` file will be created, which will be used to configure your Wispar instance and get it up and running. This process may take some time, but at the end of it you should have three running containers.

### Cloudflare/Domain Name
This step can be modified depending on how tech savvy you are, but the following is the recommended way to have free access to your Wispar instance from outside your own network.

#### Domain Name
The first step is to have a domain name you own and have access to. This can be bought from a variety of places, like [NameCheap](https://www.namecheap.com/), [Domains.com](https://www.domain.com/domains), or [Squarespace](https://domains.squarespace.com/). 

#### Clouflare Account
Once you have your domain, we recommend setting up a free [Cloudflare account](https://dash.cloudflare.com/login). From here, you will be able to set up your domain to point to your running instance of Wispar. First, you'll need to add a domain. You can find the steps to do so [here](https://dash.cloudflare.com/login). You can leave the records alone, but will need to also [update the nameservers](https://developers.cloudflare.com/fundamentals/setup/manage-domains/add-site/#2-update-nameservers), which can be done with the registrar you bought the domain from.

Following this, we will be setting up a Cloudflare Zero Trust account. Zero Trust is a free and easy way to get access to your Wispar instance. The free tier has more than enough security features, tools, and active seats to make sure only authorized users gain access. We will be creating a Self Hosted [Access Application](https://developers.cloudflare.com/cloudflare-one/applications/configure-apps/self-hosted-public-app/), creating and connecting your [Wispar instance to a tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/create-remote-tunnel/), and eventually be able to access Wispar. The links above will help you get this configured.

**NOTE: WISPAR RUNS ON PORT 1337, SO THE URL FOR YOUR TUNNEL MUST BE "localhost:1337"**. We also recommend to keep your access policies as strict as possible.

After this is done, and your Wispar instance is up and running on your machine, congratulations! You should be able to navigate to your domain, login through Cloudflare, and access Wispar!

