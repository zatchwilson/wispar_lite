from dotenv import set_key
from pathlib import Path
import getpass
import re
import string
import secrets
import subprocess
import os



symbols = ['*', '%', '!', '$', '#', '+'] # Can add more

env_file_path = Path(".env")

if not os.path.exists(env_file_path): #If an .env file already exists, it will just run the docker command to deploy

    # Validates the user's database password
    while True:
        db_pw = getpass.getpass('\nPlease enter a password for the database.\nPassword must be at least eight characters long, with one letter, number and special character (leave empty for a randomly generated password):\n')
        if not db_pw:
            for _ in range(9):
                db_pw += secrets.choice(string.ascii_lowercase)
                db_pw += secrets.choice(string.ascii_uppercase)
                db_pw += secrets.choice(string.digits)
                db_pw += secrets.choice(symbols)
            print("Your database password is " + db_pw + ".\nTo view this password, as well as all the other environment variables, open the '.env' file in your wispar project directory.")
            break
        if not re.match("^(?=.*[A-Za-z])(?=.*\\d)(?=.*[@$!%*#?&])[A-Za-z\\d@$!%*#?&]{8,}$", db_pw):
            print ("Error! Password must consist of eight characters, with one letter, number and special character!\n")
            continue
        else:
            confirm_pw = getpass.getpass("Please confirm your password.\n")

            if confirm_pw != db_pw:
                print("Error! Passwords do not match!")
                continue
            else:
                break

    # Validates the user's wispar username
    while True:
        wispar_user = input('\nPlease enter the username for your Wispar admin account (leave empty for admin):\n')
        if not wispar_user:
            wispar_user = "admin"
            break
        if not re.match("^[0-9A-Za-z_]+$", wispar_user):
            print ("Error! Please enter only letters or numbers")
            continue
        else:
            break


    while True:
        wispar_pw = getpass.getpass('\nPlease enter a password for your Wispar account.\nPassword must be at least eight characters long, with one letter, number and special character (leave empty for a randomly generated password):\n')
        if not wispar_pw:
            alphabet = string.ascii_letters + string.digits
            wispar_pw = ''.join(secrets.choice(alphabet) for i in range(13))
            print("Your admin user password is " + wispar_pw + ".\nTo view this password, as well as all the other environment variables, open the '.env' file in your wispar project directory.\n")
            break
        if not re.match("^(?=.*[A-Za-z])(?=.*\\d)(?=.*[@$!%*#?&])[A-Za-z\\d@$!%*#?&]{8,}$", wispar_pw):
            print ("Error! Password must consist of eight characters, with one letter, number and special character!\n")
            continue
        else:
            confirm_pw = getpass.getpass("Please confirm your password.\n")

            if confirm_pw != wispar_pw:
                print("Error! Passwords do not match!")
                continue
            else:
                break

    while True:
        align_answer = input('\nWould you like to align your ebook/audiobook content? [y/n] \nWARNING: THIS REQUIRES AT LEAST 24GB OF MEMORY BE AVAILABLE TO FUNCTION.\n')
        if align_answer == 'y':
            use_align = True
            break
        elif align_answer == 'n':
            use_align = False
            break
        else:
            print("Error! Please enter 'y' or 'n' for your answer!\n")

    while True:
        secret_key = input('\nPlease navigate to https://djecrety.ir/ and generate a secret key. Once that has been done, please enter it here.\n')
        if secret_key == '':
            continue
        else:
            break

    env_file_path.touch(mode=0o600, exist_ok=True)

    set_key(dotenv_path=env_file_path, key_to_set="DEBUG", value_to_set="0", quote_mode="never")
    set_key(dotenv_path=env_file_path, key_to_set="DJANGO_ALLOWED_HOSTS", value_to_set="*", quote_mode="never")
    set_key(dotenv_path=env_file_path, key_to_set="DB_HOST", value_to_set="db", quote_mode="never")
    set_key(dotenv_path=env_file_path, key_to_set="DB_ENGINE", value_to_set="django.db.backends.mysql", quote_mode="never")
    set_key(dotenv_path=env_file_path, key_to_set="DB_NAME", value_to_set="wispar_db", quote_mode="never")
    set_key(dotenv_path=env_file_path, key_to_set="DB_USER", value_to_set="root", quote_mode="never")
    set_key(dotenv_path=env_file_path, key_to_set="DB_PORT", value_to_set=3306, quote_mode="never")
    set_key(dotenv_path=env_file_path, key_to_set="DB_PASSWORD", value_to_set=str(db_pw), quote_mode="never")
    set_key(dotenv_path=env_file_path, key_to_set="CSRF_TRUSTED_ORIGINS", value_to_set="http://localhost:1337 https://localhost:1337", quote_mode="never")
    set_key(dotenv_path=env_file_path, key_to_set="DJANGO_SUPERUSER_USERNAME", value_to_set=str(wispar_user), quote_mode="never")
    set_key(dotenv_path=env_file_path, key_to_set="DJANGO_SUPERUSER_PASSWORD", value_to_set=str(wispar_pw), quote_mode="never")
    set_key(dotenv_path=env_file_path, key_to_set="DJANGO_SUPERUSER_EMAIL", value_to_set="", quote_mode="never")
    set_key(dotenv_path=env_file_path, key_to_set="USE_ALIGN", value_to_set=use_align, quote_mode="never")
    set_key(dotenv_path=env_file_path, key_to_set="DJANGO_SECRET_KEY", value_to_set=secret_key, quote_mode="never")


subprocess.Popen(["docker", "compose", "-f", "docker-compose-prod.yaml", "up", "-d", "--build"])