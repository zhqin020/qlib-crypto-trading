                handleWebSocketMessage(message) {
                    if (message.type === 'history') {
                        message.events.forEach(event => this.handleEvent(event));
                    } else {
                        this.handleEvent(message);
                    }
                },
                handleEvent(event) {
                    let title = event.type.toUpperCase();
                    let message = JSON.stringify(event.data).substring(0, 100);
                    let className = 'info';

                    if (event.type === 'mcp_tool_execution') {
                        title = `${event.data.tool}`;
                        message = `Status: ${event.data.status}`;
                        className = event.data.status === 'success' ? 'success' : 'error';
                    }

                    this.addActivity(title, message, event.timestamp, className);
                },
