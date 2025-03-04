import streamlit as st
import requests
import datetime
import csv
import io
import time  # For high-precision latency measurement
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick  # For formatting y-axis labels with a dollar sign

# Remove manual session-state initialization for dates
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

    rapidapi_key = "8e6943c05cmsh7ba5b7710610ce2p170db9jsnb665cc42e169"  # Replace with your own key
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "booking-com15.p.rapidapi.com"
    }

    # ---- Step 1: Destination Search ----
    st.subheader("Step 1: Search for a Destination")
    with st.form("destination_form"):
        location_query = st.text_input("Enter a location (city, state, country):", "")
        submitted = st.form_submit_button("1) Search Destination")
        if submitted:
            if location_query.strip():
                dest_search_url = "https://booking-com15.p.rapidapi.com/api/v1/hotels/searchDestination"
                params = {"query": location_query}
                try:
                    resp = requests.get(dest_search_url, headers=headers, params=params, timeout=10)
                    resp.raise_for_status()
                    data = resp.json() or {}
                except requests.exceptions.RequestException as e:
                    st.error(f"[Error] Could not fetch destinations: {e}")
                    st.stop()
                st.session_state.destinations_list = data.get("data", [])
                if not st.session_state.destinations_list:
                    st.warning(f"No destinations found matching '{location_query}'.")
            else:
                st.warning("No location provided. Please enter a location name.")

    if st.session_state.destinations_list:
        dest_options = [
            f"{i+1}. {d['label']} (dest_id={d.get('dest_id')}, search_type={d.get('search_type')})"
            for i, d in enumerate(st.session_state.destinations_list)
        ]
        chosen_dest_label = st.selectbox("Select a destination:", dest_options)
        if chosen_dest_label:
            chosen_index = dest_options.index(chosen_dest_label)
            chosen_dest = st.session_state.destinations_list[chosen_index]
            st.session_state.chosen_dest = chosen_dest

    # ---- Step 2: Date Range + Search Hotels (for the FIRST NIGHT) ----
    if st.session_state.chosen_dest:
        chosen_dest_id = st.session_state.chosen_dest.get("dest_id")
        chosen_search_type = st.session_state.chosen_dest.get("search_type", "CITY")
        st.write(f"You selected: {st.session_state.chosen_dest.get('label')}")
        st.write(f"dest_id={chosen_dest_id}, search_type={chosen_search_type}")
        st.subheader("Step 2: Choose date range:")
        start_date = st.date_input("Start date", datetime.date.today(), key="start_date")
        end_date = st.date_input("End date", datetime.date.today(), key="end_date")
        if start_date > end_date:
            st.warning("End date must be on or after start date.")
            st.stop()
        # Add slider to select number of pages to return (from 1 to 10)
        selected_pages = st.slider("Select number of pages to return", min_value=1, max_value=10, value=5, step=1)
        if st.button("2) Search Hotels (Uses FIRST Night)"):
            one_night_end = start_date + datetime.timedelta(days=1)
            all_hotels = []
            progress_bar_hotels = st.progress(0)
            status_text_hotels = st.empty()
            total_pages = selected_pages
            total_request_time = 0.0
            for page_num in range(1, total_pages + 1):
                req_start_time = time.perf_counter()
                search_hotels_url = "https://booking-com15.p.rapidapi.com/api/v1/hotels/searchHotels"
                params = {
                    "dest_id": chosen_dest_id,
                    "search_type": chosen_search_type,
                    "arrival_date": str(start_date),
                    "departure_date": str(one_night_end),
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
                    st.stop()
                request_latency = time.perf_counter() - req_start_time
                total_request_time += request_latency
                data_section = response_data.get("data", {})
                hotels_list = data_section.get("hotels", [])
                all_hotels.extend(hotels_list)
                progress_percentage = int((page_num / total_pages) * 100)
                avg_latency = total_request_time / page_num
                progress_bar_hotels.progress(progress_percentage)
                status_text_hotels.write(
                    f"Processed {page_num} of {total_pages} pages ({total_pages - page_num} remaining). Average latency per page: {avg_latency:.2f} seconds."
                )
            if not all_hotels:
                st.warning(f"No hotels found for the single-night search (pages 1-{total_pages}).")
                st.stop()
            st.session_state.hotels_list = all_hotels

    # ---- Step 3: Choose Hotel + Check Availability Over Full Date Range ----
    if st.session_state.hotels_list:
        st.subheader("Step 3: Select a Hotel:")
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
            start_date = st.session_state.start_date
            end_date = st.session_state.end_date
            current_night = start_date
            nightly_prices = {}
            total_nights = (end_date - start_date).days
            if total_nights <= 0:
                st.warning("Invalid date range. No nights to check.")
                st.stop()
            progress_bar = st.progress(0)
            status_text = st.empty()
            total_requests_made = 0
            total_request_time = 0.0

            while current_night < end_date:
                arrival_str = current_night.strftime("%Y-%m-%d")
                departure = current_night + datetime.timedelta(days=1)
                departure_str = departure.strftime("%Y-%m-%d")
                if departure > end_date:
                    break
                availability_url = "https://booking-com15.p.rapidapi.com/api/v1/hotels/getAvailability"
                availability_params = {
                    "hotel_id": str(chosen_hotel_id),
                    "min_date": arrival_str,
                    "max_date": departure_str,
                    "adults": "1",
                    "room_qty": "1",
                    "currency_code": "USD",
                }
                price_for_this_night = "null"
                req_start_time = time.perf_counter()
                try:
                    avail_resp = requests.get(
                        availability_url, headers=headers, params=availability_params, timeout=10
                    )
                    avail_resp.raise_for_status()
                    availability_json = avail_resp.json() or {}
                except requests.exceptions.RequestException as e:
                    st.error(f"[Error] Could not fetch availability for {arrival_str}: {e}")
                    st.stop()
                request_latency = time.perf_counter() - req_start_time
                total_requests_made += 1
                total_request_time += request_latency
                data_avail = availability_json.get("data", {})
                av_dates_list = data_avail.get("avDates", [])
                if isinstance(av_dates_list, list) and av_dates_list:
                    for date_obj in av_dates_list:
                        if isinstance(date_obj, dict):
                            for date_str_av, p_val in date_obj.items():
                                if date_str_av == arrival_str:
                                    price_for_this_night = p_val
                                    break
                            if price_for_this_night != "null":
                                break
                nightly_prices[current_night] = price_for_this_night
                current_night = departure
                progress_percentage = int((total_requests_made / total_nights) * 100)
                average_latency = total_request_time / total_requests_made
                progress_bar.progress(progress_percentage)
                status_text.write(
                    f"Processed {total_requests_made}/{total_nights} nights. Average latency per night: {average_latency:.2f} seconds."
                )

            if not nightly_prices:
                st.warning("No availability found across the specified date range.")
                st.stop()

            # Generate CSV from nightly_prices
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["night", "price"])
            for night_date in sorted(nightly_prices.keys()):
                date_str_csv = night_date.strftime("%Y-%m-%d")
                price_val = nightly_prices[night_date]
                writer.writerow([date_str_csv, price_val])
            csv_data = output.getvalue().encode("utf-8")
            st.success("CSV generated! Columns: night, price")

            # CSV download button above the graph
            st.download_button(
                label="Download availability CSV",
                data=csv_data,
                file_name="hotel_availability.csv",
                mime="text/csv"
            )

            # ----- Prepare Data for Plotting -----
            sorted_dates = sorted(nightly_prices.keys())
            plot_dates = []
            plot_prices = []
            for d in sorted_dates:
                p = nightly_prices[d]
                try:
                    p_float = float(p)
                    plot_dates.append(d)
                    plot_prices.append(p_float)
                except (ValueError, TypeError):
                    continue

            if plot_dates and plot_prices:
                st.subheader("Price Overview")
                st.caption("Note: nights with no available rooms are omitted from the plot")

                fig, ax = plt.subplots()
                ax.plot(plot_dates, plot_prices, marker='o', linestyle='-')
                ax.set_title(f"Price vs Time for {chosen_hotel_name}", fontsize=16)
                ax.set_xlabel("Date")
                ax.set_ylabel("Price (USD)")
                ax.yaxis.set_major_formatter(mtick.StrMethodFormatter('${x:,.0f}'))
                plt.xticks(rotation=45)
                st.pyplot(fig)

                buf = io.BytesIO()
                fig.savefig(buf, format="png")
                buf.seek(0)
                st.download_button(
                    label="Download Graph (.png)",
                    data=buf,
                    file_name="price_vs_day.png",
                    mime="image/png"
                )
            else:
                st.warning("No valid price data available for plotting.")

if __name__ == "__main__":
    main()
