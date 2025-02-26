import streamlit as st
import openai
import requests
import os

# Fetch API keys from secrets or environment variables
openai_api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
exchange_rate_api_key = st.secrets.get("EXCHANGE_RATE_API_KEY", os.getenv("EXCHANGE_RATE_API_KEY"))
# ---------------------------
# Conversion Data & Functions
# ---------------------------

# Note: For each category, we pick a base unit = 1.0.
# Other units have factors = 1 / (number of base units per that unit).

CONVERSION_FACTORS = {
    "Length": {
        "Meter": 1.0,
        "Kilometer": 0.001,       # 1 km = 1000 m => factor=1/1000
        "Centimeter": 100.0,      # 1 cm = 0.01 m => factor=1/0.01
        "Millimeter": 1000.0,     # 1 mm = 0.001 m
        "Mile": 0.000621371,      # 1 mile ~ 1609.34 m => factor=1/1609.34
        "Yard": 1.09361,          # 1 yd = 0.9144 m => factor=1/0.9144
        "Foot": 3.28084,          # 1 ft = 0.3048 m
        "Inch": 39.3701,          # 1 in = 0.0254 m
    },
    "Mass": {
        "Kilogram": 1.0,
        "Gram": 1000.0,
        "Milligram": 1e6,
        "Pound": 2.20462,
        "Ounce": 35.274,
    },
    "Area": {
        "Square meter": 1.0,
        "Square kilometer": 1e-6,
        "Square centimeter": 10000.0,
        "Square foot": 10.7639,
        "Square yard": 1.19599,
        "Square inch": 1550.0,
        "Acre": 0.000247105,
        "Hectare": 0.0001,
    },
    "Volume": {
        "Liter": 1.0,
        "Milliliter": 1000.0,
        "Cubic meter": 0.001,
        "US gallon": 0.264172,
        "US quart": 1.05669,
        "US pint": 2.11338,
        "US cup": 4.16667,
        "Fluid ounce": 33.814,
    },
    "Time": {
        "Second": 1.0,
        "Millisecond": 1000.0,
        "Microsecond": 1e6,
        "Minute": 0.0166667,
        "Hour": 0.000277778,
        "Day": 1.1574e-5,
        "Week": 1.6534e-6,
    },
    "Speed": {
        "Meter per second": 1.0,
        "Kilometer per hour": 3.6,
        "Mile per hour": 2.23694,
        "Foot per second": 3.28084,
        "Knot": 1.94384,
    },
    "Pressure": {
        "Pascal": 1.0,
        "Kilopascal": 0.001,
        "Bar": 1e-5,
        "PSI": 0.000145038,
        "Atmosphere": 9.86923e-6,
    },
    "Energy": {
        "Joule": 1.0,
        "Kilojoule": 0.001,
        "Calorie": 0.239006,
        "Kilocalorie": 0.000239006,
        "Watt-hour": 0.000277778,
        "Kilowatt-hour": 2.77778e-7,
        "BTU": 0.000947817,
    },
    "Data Transfer Rate": {
        "bit/s": 1.0,
        "Kilobit/s": 0.001,
        "Megabit/s": 1e-6,
        "Gigabit/s": 1e-9,
        "Byte/s": 0.125,
        "Kilobyte/s": 0.000125,
    },
    "Digital Storage": {
        "Byte": 1.0,
        "Bit": 8.0,
        "Kilobyte": 0.0009765625,
        "Megabyte": 9.5367e-7,
        "Gigabyte": 9.3132e-10,
        "Terabyte": 9.0949e-13,
    },
    "Frequency": {
        "Hertz": 1.0,
        "Kilohertz": 0.001,
        "Megahertz": 1e-6,
        "Gigahertz": 1e-9,
    },
    "Fuel Economy": {
        "L/100km": 1.0,
        "mpg (US)": 0.00425144,
        "km/L": 0.01,
    },
    "Plane Angle": {
        "Degree": 1.0,
        "Radian": 0.0174533,
        "Gradian": 1.11111,
        "Arcminute": 60.0,
        "Arcsecond": 3600.0,
    },
    # Note: Currency conversion will be handled separately.
}

# Temperature units handled via custom function
TEMPERATURE_UNITS = ["Celsius", "Fahrenheit", "Kelvin"]

def convert_temperature(value, from_unit, to_unit):
    if from_unit == to_unit:
        return value
    if from_unit == "Celsius" and to_unit == "Fahrenheit":
        return (value * 9/5) + 32
    if from_unit == "Fahrenheit" and to_unit == "Celsius":
        return (value - 32) * 5/9
    if from_unit == "Celsius" and to_unit == "Kelvin":
        return value + 273.15
    if from_unit == "Kelvin" and to_unit == "Celsius":
        return value - 273.15
    if from_unit == "Fahrenheit" and to_unit == "Kelvin":
        return (value - 32) * 5/9 + 273.15
    if from_unit == "Kelvin" and to_unit == "Fahrenheit":
        return (value - 273.15) * 9/5 + 32
    return None

def convert_units(category, value, from_unit, to_unit):
    """Generic conversion for all categories except Temperature and Currency."""
    if category == "Temperature":
        return convert_temperature(value, from_unit, to_unit)
    elif category == "Currency":
        # Currency conversion is handled separately.
        return None
    else:
        factors = CONVERSION_FACTORS.get(category, {})
        if from_unit in factors and to_unit in factors:
            base_value = value / factors[from_unit]
            return base_value * factors[to_unit]
    return None

# ---------------------------
# Currency Conversion Functions
# ---------------------------
def fetch_exchange_rates():
    """Fetch live exchange rates using ExchangeRate-API."""
    if not exchange_rate_api_key:
        st.error("Exchange Rate API key not found. Please set it in .streamlit/secrets.toml.")
        return {}
    url = f"https://v6.exchangerate-api.com/v6/{exchange_rate_api_key}/latest/USD"
    try:
        response = requests.get(url)
        data = response.json()
        if data.get("result") == "success":
            return data.get("conversion_rates", {})
        else:
            st.error("Error fetching exchange rates.")
            return {}
    except Exception as e:
        st.error(f"Error fetching exchange rates: {e}")
        return {}

def convert_currency(value, from_currency, to_currency, rates):
    if from_currency in rates and to_currency in rates:
        base_value = value / rates[from_currency]
        return base_value * rates[to_currency]
    return None

# ---------------------------
# AI Chat Assistant Function
# ---------------------------
def query_llm(prompt):
    """Query OpenAI's ChatGPT API for answers."""
    if not openai_api_key:
        return "API key not found. Please set it in .streamlit/secrets.toml or environment variables."

    try:
        if not openai_api_key:
            return "API key not found. Please set it in .streamlit/secrets.toml."
        openai.api_key = openai_api_key
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant for unit and currency conversions."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error querying AI: {e}"
    
# ---------------------------
# Main App Function
# ---------------------------
def main():
    st.set_page_config(page_title="Advanced Unit & Currency Converter with AI Assistant", layout="wide")
    st.title("🌐 Advanced Unit & Currency Converter with AI Assistant")
    
    # Sidebar: Converter Settings
    st.sidebar.header("Converter Settings")
    # Add "Currency" to the list of categories
    all_categories = sorted(list(CONVERSION_FACTORS.keys()) + ["Temperature", "Currency"])
    category = st.sidebar.selectbox("Select Conversion Category", options=all_categories)
    
    # Determine unit options based on category
    if category == "Temperature":
        units = TEMPERATURE_UNITS
    elif category == "Currency":
        exchange_rates = fetch_exchange_rates()
        units = sorted(list(exchange_rates.keys())) if exchange_rates else []
    else:
        units = list(CONVERSION_FACTORS.get(category, {}).keys())
    
    from_unit = st.sidebar.selectbox("From Unit", options=units, index=0)
    to_unit = st.sidebar.selectbox("To Unit", options=units, index=0)
    value = st.sidebar.number_input("Enter value to convert", value=1.0)
    
    if st.sidebar.button("Convert"):
        if category == "Currency":
            rates = fetch_exchange_rates()
            result = convert_currency(value, from_unit, to_unit, rates)
        else:
            result = convert_units(category, value, from_unit, to_unit)
        if result is not None:
            st.sidebar.success(f"Result: {result:.4f} {to_unit}")
        else:
            st.sidebar.error("Conversion error. Please check your inputs.")
    
    # Main Area: Detailed Converter
    st.header("Converter")
    st.write(f"Converting **{value} {from_unit}** to **{to_unit}** in category **{category}**.")
    if category == "Currency":
        rates = fetch_exchange_rates()
        conversion_result = convert_currency(value, from_unit, to_unit, rates)
    else:
        conversion_result = convert_units(category, value, from_unit, to_unit)
    if conversion_result is not None:
        st.markdown("### Conversion Result")
        st.write(f"**{conversion_result:.4f} {to_unit}**")
    else:
        st.write("Conversion error. Please verify your inputs.")
    
    st.markdown("---")
    
    # AI Assistant Section with input and button on the same row
    st.header("AI Assistant")
    st.write("Ask questions about unit or currency conversions, measurement systems, or related topics.")
    ai_col1, ai_col2 = st.columns([4,1])
    with ai_col1:
        user_query = st.text_input("Your question for the AI:", "")
        ask_button = st.button("Ask AI")
    if ask_button:
        if user_query.strip():
            prompt = (f"Provide a concise, clear answer to the following question related to unit/currency conversions and measurement systems: {user_query}")
            with st.spinner("Processing your query..."):
                ai_response = query_llm(prompt)
            st.markdown("### AI Response")
            st.write(ai_response)
        else:
            st.warning("Please enter a question.")

if __name__ == "__main__":
    main()
