from http_layer import test_servicenow_connection, get_auth_info

def nowtest():
    """Test function to verify mcp is running."""
    return "Server is running and ready to handle requests!"

async def now_test_connection():
    """Test the configured Basic Auth connection to ServiceNow."""
    result = await test_servicenow_connection()
    return result

def now_auth_info():
    """Get information about current authentication configuration."""
    return get_auth_info()
