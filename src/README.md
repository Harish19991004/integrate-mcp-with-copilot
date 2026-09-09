# Mergington High School Activities API

A super simple FastAPI application that allows students to view and sign up for extracurricular activities.

## Features

- View all available extracurricular activities
- Create student accounts and sign in
- Sign up for activities with participant and optional team details

## Getting Started

1. Install the dependencies:

   ```
   pip install fastapi uvicorn
   ```

2. Run the application:

   ```
   python app.py
   ```

3. Open your browser and go to:
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Get all activities with their details and current participant count |
| POST   | `/auth/signup`                                                     | Create a student account and start a session                         |
| POST   | `/auth/login`                                                      | Sign in and receive a session token                                  |
| POST   | `/auth/logout`                                                     | End the current session                                              |
| GET    | `/auth/me`                                                         | Get the signed-in account                                            |
| POST   | `/activities/{activity_name}/signup`                              | Register an authenticated student for an activity                    |
| DELETE | `/activities/{activity_name}/unregister?email=...`                | Unregister yourself, or another student as an admin                  |

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:

   - Description
   - Schedule
   - Maximum number of participants allowed
   - List of student emails who are signed up

2. **Students** - Uses email as identifier:
   - Name
   - Password hash
   - Role (`student` or `admin`)
   - Expiring session tokens

3. **Registrations** - Uses activity name and student email as a composite identifier:
   - Participant name
   - Optional team name

Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` before starting the app to bootstrap an
administrator account. New accounts always receive the `student` role.

Activity and participant data is stored in a local SQLite database at
`src/activities.sqlite` by default. Set the `ACTIVITY_DB_PATH` environment
variable to use a different database location.
