from app.blocks.schema import FlowBlock, CompareBlock, AnswerBlock, ChecklistBlock
from app.blocks.flow import render_flow
from app.blocks.compare import render_compare
from app.blocks.answer import render_answer
from app.blocks.checklist import render_checklist
from app.commands import resolve_ref_element

def test_flow():
    flow_data = FlowBlock(
        title='Order Fulfillment',
        nodes=[
            {'id': 'n1', 'label': 'Receive Order', 'shape': 'start', 'note': 'Webhook triggers'},
            {'id': 'n2', 'label': 'Check Inventory', 'shape': 'decision', 'highlight': True},
            {'id': 'n3', 'label': 'Ship Item', 'shape': 'step'},
            {'id': 'n4', 'label': 'Order Complete', 'shape': 'end'}
        ],
        edges=[
            {'from': 'n1', 'to': 'n2'},
            {'from': 'n2', 'to': 'n3', 'label': 'in stock'},
            {'from': 'n3', 'to': 'n4'}
        ]
    )
    svg = render_flow(flow_data)
    assert '<svg' in svg
    assert 'data-ref="n1"' in svg
    assert 'data-ref="n2"' in svg
    desc, kind = resolve_ref_element('flow', flow_data.model_dump(), 'n2')
    assert 'Check Inventory' in desc
    print('Flow test passed')

def test_compare():
    comp_data = CompareBlock(
        title='Cloud Providers',
        options=['GCP', 'AWS'],
        criteria=['Pricing', 'Speed'],
        cells=[['Low', 'Medium'], ['Fast', 'Fast']],
        recommendation='GCP is recommended for this project'
    )
    html_comp = render_compare(comp_data)
    assert '<table' in html_comp
    assert 'data-ref="cell:0:0"' in html_comp
    desc, kind = resolve_ref_element('compare', comp_data.model_dump(), 'cell:0:0')
    assert 'Pricing' in desc
    print('Compare test passed')

def test_answer():
    ans_data = AnswerBlock(
        question='What is the timeout on Cloud Run?',
        answer='Cloud Run supports request timeouts up to 3600 seconds.',
        detail='Recommended for long-running WebSockets.',
        sources=[{'title': 'Cloud Run Docs', 'url': 'https://cloud.google.com/run'}],
        confidence='high'
    )
    html_ans = render_answer(ans_data)
    assert 'data-ref="src:0"' in html_ans
    assert 'confidence-high' in html_ans
    desc, kind = resolve_ref_element('answer', ans_data.model_dump(), 'src:0')
    assert 'Cloud Run Docs' in desc
    print('Answer test passed')

def test_checklist():
    chk_data = ChecklistBlock(
        title='Pre-flight Checklist',
        items=[
            {'text': 'Configure ADC credentials', 'owner': 'Dev', 'done': True},
            {'text': 'Verify WebSocket streaming', 'owner': 'Team', 'done': False}
        ]
    )
    html_chk = render_checklist(chk_data)
    assert 'data-ref="item:0"' in html_chk
    assert 'data-ref="item:1"' in html_chk
    desc, kind = resolve_ref_element('checklist', chk_data.model_dump(), 'item:1')
    assert 'Verify WebSocket streaming' in desc
    print('Checklist test passed')

if __name__ == '__main__':
    test_flow()
    test_compare()
    test_answer()
    test_checklist()
    print('ALL BLOCK TESTS PASSED SUCCESSFULLY!')
