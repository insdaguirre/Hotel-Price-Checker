import streamlit as st
import requests
import datetime
import csv
import io

# Initialize session state variables, if they don't exist yet
if "destinations_list" not in st.session_state:
    st.session_state.destinations_list = []
if "chosen_dest" not in st.session_state:
    st.session_state.chosen_dest = None
if "hotels_list" not in st.session_state:
    st.session_state.hotels_list = []
if "chosen_hotel" not in st.session_state:
    st.session_state.chosen_hotel = None

def main():
    st.title("Hotel Price Checker")

    rapidapi_key = "8e6943c05cmsh7ba5b7710610ce2p170db9jsnb665cc42e169"  # replace with yours
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "booking-com15.p.rapidapi.com"
    }

    # ---- Step 1: Destination Search ----
    # ---- Step 1: Destination Search ----
    st.subheader("Step 1: Search for a Destination")

    with st.form("destination_form"):
        location_query = st.text_input("Enter a location (city, state, country):", "")
        submitted = st.form_submit_button("1) Search Destination")

        if submitted:
            if location_query.strip():
                # Call the searchDestination endpoint
                dest_search_url = "https://booking-com15.p.rapidapi.com/api/v1/hotels/searchDestination"
                params = {"query": location_query}
                try:
                    resp = requests.get(dest_search_url, headers=headers, params=params, timeout=10)
                    resp.raise_for_status()
                    data = resp.json() or {}
                except requests.exceptions.RequestException as e:
                    st.error(f"[Error] Could not fetch destinations: {e}")
                    return  # <--- valid, because we are inside main()

                st.session_state.destinations_list = data.get("data", [])

                if not st.session_state.destinations_list:
                    st.warning(f"No destinations found matching '{location_query}'.")
            else:
                st.warning("No location provided. Please enter a location name.")


    # If we already have destinations, let user pick from them
    if st.session_state.destinations_list:
        dest_options = [
            f"{i+1}. {d['label']} (dest_id={d.get('dest_id')}, search_type={d.get('search_type')})"
            for i, d in enumerate(st.session_state.destinations_list)
        ]
        chosen_dest_label = st.selectbox("Select a destination:", dest_options)

        # figure out which item is chosen
        if chosen_dest_label:
            chosen_index = dest_options.index(chosen_dest_label)
            chosen_dest = st.session_state.destinations_list[chosen_index]
            st.session_state.chosen_dest = chosen_dest  # store in session_state

    # ---- Step 2: Date Range + Search Hotels ----
    if st.session_state.chosen_dest:
        chosen_dest_id = st.session_state.chosen_dest.get("dest_id")
        chosen_search_type = st.session_state.chosen_dest.get("search_type", "CITY")
        st.write(f"You selected: {st.session_state.chosen_dest.get('label')}")
        st.write(f"dest_id={chosen_dest_id}, search_type={chosen_search_type}")

        # date inputs
        st.subheader("Step 2: Choose date range:")
        start_date = st.date_input("Start date", datetime.date.today(), key="start_date")
        end_date = st.date_input("End date", datetime.date.today(), key="end_date")

        if start_date > end_date:
            st.warning("End date must be on or after start date.")
            return

        start_date_str = str(start_date)
        end_date_str = str(end_date)

        if st.button("2) Search Hotels for this Destination"):
            all_hotels = []

            # Loop through pages 1 to 3, this can be adjusted 
            for page_num in range(1, 4):
                search_hotels_url = "https://booking-com15.p.rapidapi.com/api/v1/hotels/searchHotels"
                params = {
                    "dest_id": chosen_dest_id,
                    "search_type": chosen_search_type,
                    "arrival_date": start_date_str,
                    "departure_date": end_date_str,
                    "adults": "1",
                    "room_qty": "1",
                    "page_number": str(page_num),
                    "units": "metric",
                    "temperature_unit": "c",
                    "languagecode": "en-us",
                    "currency_code": "USD",
                }
                try:
                    hotels_resp = requests.get(search_hotels_url, headers=headers, params=params, timeout=10)
                    hotels_resp.raise_for_status()
                    response_data = hotels_resp.json() or {}
                except requests.exceptions.RequestException as e:
                    st.error(f"[Error] Could not fetch hotels on page {page_num}: {e}")
                    return  # <--- still valid, inside main()

                data_section = response_data.get("data", {})
                hotels_list = data_section.get("hotels", [])
                all_hotels.extend(hotels_list)

            if not all_hotels:
                st.warning("No hotels found for the given criteria (pages 1-3).")
                return

            # store the combined hotels in session state
            st.session_state.hotels_list = all_hotels

    # ---- Step 3: Choose Hotel + Availability ----
    if st.session_state.hotels_list:
        st.subheader("Step 3: Select a hotel:")
        hotel_options = [
            f"{i+1}. {h['property']['name']} (hotel_id={h['property'].get('id')})"
            for i, h in enumerate(st.session_state.hotels_list)
        ]
        chosen_hotel_label = st.selectbox("Choose a hotel:", hotel_options)

        if chosen_hotel_label:
            chosen_hotel_index = hotel_options.index(chosen_hotel_label)
            chosen_hotel = st.session_state.hotels_list[chosen_hotel_index]
            st.session_state.chosen_hotel = chosen_hotel

    if st.session_state.chosen_hotel:
        chosen_prop = st.session_state.chosen_hotel.get("property", {})
        chosen_hotel_id = chosen_prop.get("id")
        chosen_hotel_name = chosen_prop.get("name", "Unknown Hotel")

        st.write(f"You selected: {chosen_hotel_name} (hotel_id={chosen_hotel_id})")

        check_availability_btn = st.button("3) Check Availability & Generate CSV")
        if check_availability_btn and chosen_hotel_id:
            # prepare date range from session_state keys
            start_date = st.session_state.start_date
            end_date = st.session_state.end_date
            start_date_str = str(start_date)
            end_date_str = str(end_date)

            availability_url = "https://booking-com15.p.rapidapi.com/api/v1/hotels/getAvailability"
            availability_params = {
                "hotel_id": str(chosen_hotel_id),
                "min_date": start_date_str,
                "max_date": end_date_str,
                "adults": "1",
                "room_qty": "1",
                "currency_code": "USD"
            }

            try:
                avail_resp = requests.get(
                    availability_url, headers=headers, params=availability_params, timeout=10
                )
                avail_resp.raise_for_status()
                availability_json = avail_resp.json() or {}
            except requests.exceptions.RequestException as e:
                st.error(f"[Error] Could not fetch availability: {e}")
                return

            data_avail = availability_json.get("data", {})
            av_dates_list = data_avail.get("avDates", [])

            if not isinstance(av_dates_list, list) or not av_dates_list:
                st.warning("No 'avDates' found in availability response.")
                st.write("Full response:", availability_json)
                return

            # Parse avDates, keep min price
            lowest_prices = {}
            for date_obj in av_dates_list:
                if not isinstance(date_obj, dict):
                    continue
                for date_str_av, price_val in date_obj.items():
                    try:
                        parsed_date = datetime.datetime.strptime(date_str_av, "%Y-%m-%d").date()
                    except ValueError:
                        continue
                    if start_date <= parsed_date <= end_date:
                        current_price = lowest_prices.get(parsed_date)
                        if current_price is None or price_val < current_price:
                            lowest_prices[parsed_date] = price_val

            if not lowest_prices:
                st.warning("No availability within the specified date range.")
                return

            # Write CSV
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["night", "price"])
            for date_obj in sorted(lowest_prices.keys()):
                date_str_csv = date_obj.strftime("%Y-%m-%d")
                price_val = lowest_prices[date_obj]
                writer.writerow([date_str_csv, price_val])

            csv_data = output.getvalue().encode("utf-8")
            st.success("CSV generated! Columns: night, price")

            # Provide a download button
            st.download_button(
                label="Download availability CSV",
                data=csv_data,
                file_name="hotel_availability.csv",
                mime="text/csv"
            )

if __name__ == "__main__":
    main()
