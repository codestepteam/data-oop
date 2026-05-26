import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';

// Mock ReactFlow so that it renders a simple container instead of crashing in jsdom
vi.mock('@xyflow/react', () => {
  return {
    ReactFlow: ({ children, nodes }: any) => (
      <div data-testid="react-flow">
        {children}
        {nodes?.map((n: any) => (
          <div key={n.id} data-testid={`flow-node-${n.id}`}>
            {n.data?.label}
          </div>
        ))}
      </div>
    ),
    Background: () => <div data-testid="react-flow-background" />,
    Controls: () => <div data-testid="react-flow-controls" />,
    MarkerType: { ArrowClosed: 'arrowclosed' }
  };
});

describe('TBox & Workflow Studio UI App', () => {
  let mockFetch: any;

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch = vi.fn().mockImplementation((url: string, options?: any) => {
      if (url === '/api/tbox') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            classes: [
              { name: 'Product', label: 'Product', description: 'Product class', properties: [
                { name: 'name', datatype: 'string', required: true, unique: false, nullable: true, default: null }
              ], interfaces: [] },
              { name: 'Event', label: 'Event', description: 'Event class', properties: [], interfaces: [] }
            ],
            interfaces: [],
            properties: [],
            relationships: [
              { id: 'rel1', name: 'INCLUDES', from_class: 'Event', to_class: 'Product', min_count: 0, max_count: null, required: false, description: null }
            ],
            constraints: []
          })
        });
      }
      if (url === '/api/workflows') {
        if (options && options.method === 'POST') {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ status: 'success', uuid: 'wf-1234' })
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([
            {
              name: 'add event',
              description: 'event event',
              steps: [
                { step_id: 'step_1', action: 'create_node', class_name: 'Event', properties: { name: '{name}' } }
              ],
              parameters: [
                { name: 'name', type: 'string', required: true, description: 'event name' }
              ],
              uuid: 'wf-123'
            }
          ])
        });
      }
      if (url === '/api/workflows/parameter-types') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(["string", "integer", "boolean", "uuid", "array"])
        });
      }
      if (url === '/api/workflows/dsl') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ status: 'success', dsl: '# Generated Python DSL Code' })
        });
      }
      if (url === '/api/validation/latest') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ run: null, issues: [] })
        });
      }
      if (url === '/api/abox/nodes') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ counts: [], nodes: [] })
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({})
      });
    });
    globalThis.fetch = mockFetch;
  });

  it('renders studio and navigates between tabs', async () => {
    render(<App />);

    // Main header check
    expect(screen.getByText(/Data OOP Studio/i)).toBeInTheDocument();

    // Renders TBox Schema by default
    expect(screen.getByText(/TBox Definitions/i)).toBeInTheDocument();

    // Navigate to Workflow Studio
    const workflowTabButton = screen.getByText(/^Workflow Builder$/);
    fireEvent.click(workflowTabButton);

    // Saved workflows heading and loaded workflow list visible
    await waitFor(() => {
      expect(screen.getByText(/Saved Workflows/i)).toBeInTheDocument();
      expect(screen.getByText(/add event/i)).toBeInTheDocument();
    });
  });

  it('allows loading a workflow, adding steps, creating relationships and handling parameters', async () => {
    render(<App />);

    // Go to workflow studio
    const workflowTabButton = screen.getByText(/^Workflow Builder$/);
    fireEvent.click(workflowTabButton);

    // Load workflow
    const wfButton = await screen.findByText('add event');
    fireEvent.click(wfButton);

    // Verify fields populated
    expect(screen.getByDisplayValue('add event')).toBeInTheDocument();
    expect(screen.getByText('{name}')).toBeInTheDocument();

    // Test: Adding a node step
    const addNodeButton = screen.getByText(/Add Node Step/i);
    fireEvent.click(addNodeButton);

    // Verify new step created (two steps total now)
    expect(await screen.findByText(/step_2/i)).toBeInTheDocument();

    // Test: Adding a relationship step
    const addRelButton = screen.getByText(/Add Link Step/i);
    fireEvent.click(addRelButton);
    expect(await screen.findByText(/step_3/i)).toBeInTheDocument();

    // Test: Parameters section addition form
    const varNameInput = screen.getByPlaceholderText(/Variable name/i);
    fireEvent.change(varNameInput, { target: { value: 'custom_param' } });

    const addParamButton = screen.getByRole('button', { name: /^Add$/ });
    fireEvent.click(addParamButton);

    // Verify param is declared
    expect(screen.getByText('{custom_param}')).toBeInTheDocument();
  });
});
