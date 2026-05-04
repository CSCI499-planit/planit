# Server Endpoints
- Guide to each endpoint available in backend API: 'https://planit-backend-57li.onrender.com'
- Note: ensure that requests are being done from a valid origin listed in server/main
- Note: When frontend is hosted, add live URL to PRODUCTION_URL env variables

## User Endpoint

### /user/signup :POST
- Used to create new user accounts

### /user/signin :POST
- Used to sign in existing users

### /user/signout :POST
- Used to sign out user

### /user/users :GET
- Used to return all user data

## Preference Endpoint

### /preference :POST
- Used to submit preference form

### /preference :GET
- Used to view the current user's preference form

### /preference :PUT
- Used to update the current user's preference form

### /preference :DELETE
- Used to delete the current user's preference form

## Recommend Endpoint

### /recommend/places : POST
- Takes a user's request of desired place (location, amount of places, max distance) & returns a list of recommended places

### /recommend/itinerary : POST
- Takes a user's request of desired trip (location, length of trip, date of trip, amount of places, max distance between places) & returns a list of the recommended itinerary

## Interactions Endpoint

### /interactions : POST
- Logs a user interaction (liking/disliking an itinerary, liking/disliking a place, importing Google Takeout data)

### /interactions : GET
- Returns a user interactions