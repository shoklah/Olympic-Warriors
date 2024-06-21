# Olympic-Warriors
Django Application to manage sport events

This repository contains a Django application configured to run within a Docker Compose environment, facilitating a seamless development setup. By using Docker Compose, you can easily spin up the necessary services and dependencies, ensuring a consistent and reproducible development environment.

## Prerequisites

Make sure you have the following installed on your machine:

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)
- [Python](https://www.python.org/downloads/) (for local development without Docker)

## Getting Started

1. Clone this repository to your local machine:

   ```bash
   git clone https://github.com/shoklah/Olympic-Warriors.git
   ```

2. Navigate to the project directory:

   ```bash
   cd Olympic-Warriors
   ```

3. Create `prod.env` and `dev.env` files in the root of the project and configure your Django settings for production and development respectively. You can use the provided `.env.example` as a template.

4. Build and start the Docker containers:

   ```bash
   docker-compose up --build
   ```

   This will start the Django development server, along with any necessary dependencies specified in the `docker-compose.yml` file.

5. Open your web browser and visit [http://localhost:3003](http://localhost:3003) to access your Django application.

## Development

If you prefer to run the Django application locally without Docker, you can create a virtual environment and install the dependencies specified in the `requirements.txt` file:

```bash
python -m venv venv
source venv/bin/activate  # On Windows, use 'venv\Scripts\activate'
pip install -r requirements.txt
```

Then, migrate the database and run the development server:

```bash
python manage.py migrate
python manage.py runserver
```

Visit [http://localhost:8000](http://localhost:8000) to access your Django application.

## Docker Compose Configuration

The `docker-compose.yml` file includes configurations for the following services:

- `app`: Django application server
- `db`: PostgreSQL database server
- `pgadmin`: PostgreSQL database management tool

Feel free to customize these configurations based on your project requirements.

## Production

To deploy the application in production, refer to [those steps](https://www.digitalocean.com/community/tutorials/how-to-set-up-django-with-postgres-nginx-and-gunicorn-on-ubuntu).

Alternatively, you can use the docker-compose configuration and setup a reverse proxy on [http://localhost:3003](http://localhost:3003).

## Notes

- Make sure to update the Django `SECRET_KEY` and other sensitive information in the `.env` file.

Happy coding! 🚀
