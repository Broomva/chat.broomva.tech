# Use a specific platform
FROM --platform=linux/amd64 python:3.11

# Create a new user
RUN useradd -m -u 1000 user

# Switch to the new user
USER user

# Set environment variables
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Set the working directory
WORKDIR $HOME/app

# Copy the entire project to the container
COPY --chown=user . $HOME/app

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && poetry config virtualenvs.create false

# Ensure all packages are installed to a user-owned directory
ENV POETRY_HOME=$HOME/.poetry \
    PYTHONUSERBASE=$HOME/.python_packages \
    PATH=$POETRY_HOME/bin:$PYTHONUSERBASE/bin:$PATH

# Install project dependencies using poetry
RUN poetry install --only main

# The command that starts your application
CMD ["chainlit", "run", "app.py", "--port", "10000"]
