import streamlit as st
import replicate
from supabase import create_client
import os
import requests
from PIL import Image
from io import BytesIO
from datetime import datetime
import time

# Configuração das credenciais via environment variables
supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)

# Configurar Replicate API Token explicitamente
os.environ['REPLICATE_API_TOKEN'] = os.getenv('REPLICATE_API_TOKEN')

# Configurar o estado da sessão
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = None


def save_generation(user_id, image_link, prompt_used):
    """Save generated image info to database"""
    try:
        result = supabase.table('generations').insert({
            "user_id": user_id,
            "image_link": image_link,
            "prompt_used": prompt_used
        }).execute()
        return True
    except Exception as e:
        return False


def get_user_generations(user_id):
    """Get user's generation history"""
    try:
        st.write("Debug - Fetching generations for user:", user_id)
        response = supabase.table('generations').select("*").eq('user_id', user_id).order('created_at.desc').execute()
        st.write("Debug - Fetch response:", response)
        return response.data
    except Exception as e:
        st.error(f"Error fetching generations: {str(e)}")
        return []


def create_account(username, password):
    """Create a new user account"""
    try:
        response = supabase.table('users').select("*").eq('username', username).execute()
        if len(response.data) > 0:
            return False, "Username already exists"

        response = supabase.table('users').insert({
            "username": username,
            "password": password
        }).execute()

        return True, response.data[0]['id']
    except Exception as e:
        return False, str(e)


def login(username, password):
    """Authenticate user login"""
    try:
        response = supabase.table('users').select("*").eq('username', username).eq('password', password).execute()
        if len(response.data) > 0:
            return True, response.data[0]['id']
        return False, "Invalid credentials"
    except Exception as e:
        return False, str(e)


def load_image_from_url(url):
    """Load image from URL"""
    try:
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))
        return img
    except Exception as e:
        st.error(f"Error loading image: {str(e)}")
        return None


def format_date(date_str):
    """Format date string to readable format"""
    try:
        date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return date.strftime("%B %d, %Y %I:%M %p")
    except:
        return date_str


def main():
    # Configuração da página
    st.set_page_config(
        page_title="AI Image Creator",
        page_icon="🎨",
        layout="wide"
    )

    # CSS customizado
    st.markdown("""
        <style>
        .stButton>button {
            width: 100%;
        }
        .gallery-image {
            margin-bottom: 1rem;
        }
        .prompt-text {
            color: #666;
            font-size: 0.9em;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("🎨 AI Image Creator")

    # Sidebar
    with st.sidebar:
        if st.session_state.logged_in:
            st.markdown(f"### 👋 Welcome, {st.session_state.username}!")
            st.write("Debug - Current user ID:", st.session_state.user_id)
            if st.button("🚪 Logout", key="logout"):
                st.session_state.logged_in = False
                st.session_state.user_id = None
                st.session_state.username = None
                st.rerun()

    if not st.session_state.logged_in:
        col1, col2 = st.columns(2)

        with col1:
            st.header("🔑 Login")
            login_username = st.text_input("Username", key="login_username")
            login_password = st.text_input("Password", type="password", key="login_password")
            if st.button("Login", key="login_button"):
                success, result = login(login_username, login_password)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.user_id = result
                    st.session_state.username = login_username
                    st.rerun()
                else:
                    st.error(result)

        with col2:
            st.header("✨ Create Account")
            new_username = st.text_input("Username", key="new_username")
            new_password = st.text_input("Password", type="password", key="new_password")
            if st.button("Create Account", key="create_account"):
                success, result = create_account(new_username, new_password)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.user_id = result
                    st.session_state.username = new_username
                    st.success("Account created successfully!")
                    st.rerun()
                else:
                    st.error(result)

    else:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.header("🎨 Create New Image")
            prompt = st.text_area("Enter your prompt:", height=100)
            if st.button("🚀 Generate Image", use_container_width=True):
                if prompt:
                    with st.spinner("✨ Generating your masterpiece... This might take a minute."):
                        try:
                            # Debug information
                            st.write("Starting generation...")
                            st.write("Current user ID:", st.session_state.user_id)

                            output = replicate.run(
                                "black-forest-labs/flux-schnell",
                                input={
                                    "prompt": prompt,
                                    "num_inference_steps": 4,
                                    "guidance_scale": 7.5,
                                    "negative_prompt": "ugly, deformed, broken, blurry, bad quality, distorted"
                                }
                            )

                            st.write("Generation output:", output)

                            if output and isinstance(output, list) and len(output) > 0:
                                # Convert the FileOutput object to a string URL
                                image_url = str(output[0])
                                st.write("Image URL:", image_url)

                                # Try to load the image
                                img = load_image_from_url(image_url)
                                if img:
                                    st.session_state.last_image = image_url
                                    st.write("Image loaded successfully, attempting to save...")

                                    # Try to save to database
                                    save_success = save_generation(st.session_state.user_id, image_url, prompt)

                                    if save_success:
                                        st.success("✨ Image generated and saved successfully!")
                                        # Check what's in the database right after saving
                                        generations = get_user_generations(st.session_state.user_id)
                                        st.write("Current generations in database:", generations)
                                        time.sleep(1)  # Wait a bit before reloading
                                        st.rerun()
                                    else:
                                        st.error("Failed to save to database. Check the error messages above.")
                                else:
                                    st.error("Failed to load the generated image")
                            else:
                                st.error("No output received from the model")

                        except Exception as e:
                            st.error("Full error details:")
                            st.error(str(e))
                            st.error("Type of error:", type(e).__name__)
                else:
                    st.warning("Please enter a prompt first!")

        with col2:
            st.header("🖼️ Latest Creation")
            if 'last_image' in st.session_state:
                try:
                    img = load_image_from_url(st.session_state.last_image)
                    if img:
                        st.image(img, use_container_width=True)
                except Exception as e:
                    st.error(f"Error displaying latest image: {str(e)}")

        # Gallery de imagens geradas
        st.markdown("---")
        st.header("🗂️ Your Image Gallery")
        generations = get_user_generations(st.session_state.user_id)

        if generations:
            cols = st.columns(3)
            for idx, generation in enumerate(generations):
                with cols[idx % 3]:
                    try:
                        img = load_image_from_url(generation['image_link'])
                        if img:
                            st.image(img, use_container_width=True)
                            with st.expander("📝 Image Details"):
                                st.markdown(f"**Prompt:** {generation['prompt_used']}")
                                st.markdown(f"**Created:** {format_date(generation['created_at'])}")
                    except Exception as e:
                        st.error(f"Error loading gallery image: {str(e)}")
        else:
            st.info("🎨 You haven't generated any images yet. Try creating one!")


if __name__ == "__main__":
    main()