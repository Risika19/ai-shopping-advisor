import json
from django.test import TestCase
from django.urls import reverse
from .models import ChatSession, ChatMessage, MessageFeedback, SearchAnalytics
from .utils import (
    _extract_budget, _extract_category, _extract_brand,
    _extract_all_specs, detect_intent, filter_products, generate_product_card,
    generate_comparison_table, ask_assistant, generate_title, _extract_filters,
    ConversationContext, _handle_refinement, _generate_follow_up, _format_with_follow_up,
    INTENT_GREETING, INTENT_GOODBYE, INTENT_THANKS, INTENT_HELP,
    INTENT_RECOMMENDATION, INTENT_COMPARISON, INTENT_GENERAL, INTENT_PRODUCT_DETAILS,
)
from .services import rank_by_similarity, find_similar_products
from products.models import Product


class ChatbotURLTest(TestCase):
    def test_chatbot_page_status(self):
        response = self.client.get(reverse('chatbot_view'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'chatbot/chatbot.html')

    def test_chatbot_post_empty_message(self):
        response = self.client.post(reverse('chatbot_view'), {'message': ''})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])

    def test_new_chat_endpoint(self):
        response = self.client.post(reverse('chatbot_new_chat'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('session_id', data)

    def test_delete_all_endpoint(self):
        self.client.post(reverse('chatbot_new_chat'))
        response = self.client.post(reverse('chatbot_delete_all'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

    def test_list_sessions(self):
        self.client.post(reverse('chatbot_new_chat'))
        response = self.client.get(reverse('chatbot_sessions'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('groups', data)

    def test_get_session(self):
        resp = self.client.post(reverse('chatbot_new_chat'))
        sid = resp.json()['session_id']
        response = self.client.get(reverse('chatbot_get_session', args=[sid]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], sid)

    def test_rename_session(self):
        resp = self.client.post(reverse('chatbot_new_chat'))
        sid = resp.json()['session_id']
        response = self.client.post(
            reverse('chatbot_rename_session', args=[sid]),
            {'title': 'My Chat'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['title'], 'My Chat')

    def test_delete_session(self):
        resp = self.client.post(reverse('chatbot_new_chat'))
        sid = resp.json()['session_id']
        response = self.client.post(reverse('chatbot_delete_session', args=[sid]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ChatSession.objects.filter(id=sid).exists())

    def test_export_txt(self):
        resp = self.client.post(reverse('chatbot_new_chat'))
        sid = resp.json()['session_id']
        response = self.client.get(reverse('chatbot_export_txt', args=[sid]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain; charset=utf-8')

    def test_export_md(self):
        resp = self.client.post(reverse('chatbot_new_chat'))
        sid = resp.json()['session_id']
        response = self.client.get(reverse('chatbot_export_md', args=[sid]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/markdown; charset=utf-8')

    def test_feedback_endpoint(self):
        self.client.post(reverse('chatbot_view'), {'message': 'Hi'})
        msg = ChatMessage.objects.filter(role='assistant').first()
        if msg:
            response = self.client.post(reverse('chatbot_feedback'), {
                'message_id': msg.id, 'rating': 'thumbs_up'
            })
            self.assertEqual(response.status_code, 200)

    def test_regenerate_endpoint(self):
        self.client.post(reverse('chatbot_view'), {'message': 'Hi'})
        resp = self.client.post(reverse('chatbot_new_chat'))
        self.client.post(reverse('chatbot_view'), {'message': 'Samsung phone', 'session_id': resp.json()['session_id']})
        response = self.client.post(reverse('chatbot_regenerate'), {
            'session_id': resp.json()['session_id']
        })
        self.assertEqual(response.status_code, 200)


class IntentDetectionTest(TestCase):
    def test_greeting_intents(self):
        self.assertEqual(detect_intent('Hi'), INTENT_GREETING)
        self.assertEqual(detect_intent('Hello'), INTENT_GREETING)
        self.assertEqual(detect_intent('Good Morning'), INTENT_GREETING)
        self.assertEqual(detect_intent('How are you?'), INTENT_GREETING)

    def test_goodbye_intents(self):
        self.assertEqual(detect_intent('Bye'), INTENT_GOODBYE)
        self.assertEqual(detect_intent('Goodbye'), INTENT_GOODBYE)
        self.assertEqual(detect_intent('See you'), INTENT_GOODBYE)

    def test_thanks_intents(self):
        self.assertEqual(detect_intent('Thank you'), INTENT_THANKS)
        self.assertEqual(detect_intent('Thanks!'), INTENT_THANKS)

    def test_help_intent(self):
        self.assertEqual(detect_intent('Help'), INTENT_HELP)
        self.assertEqual(detect_intent('What can you do?'), INTENT_HELP)

    def test_comparison_intent(self):
        self.assertEqual(detect_intent('Compare iPhone 15 and Galaxy S24'), INTENT_COMPARISON)
        self.assertEqual(detect_intent('iPhone vs Samsung'), INTENT_COMPARISON)

    def test_recommendation_intent(self):
        self.assertEqual(detect_intent('Suggest a laptop'), INTENT_RECOMMENDATION)
        self.assertEqual(detect_intent('Find me a phone'), INTENT_RECOMMENDATION)

    def test_product_details_intent(self):
        self.assertEqual(detect_intent('Tell me about Galaxy S24'), INTENT_PRODUCT_DETAILS)
        self.assertEqual(detect_intent('Show me MacBook Air'), INTENT_PRODUCT_DETAILS)

    def test_general_intent(self):
        self.assertEqual(detect_intent('What is the weather?'), INTENT_GENERAL)
        self.assertEqual(detect_intent('Tell me a joke'), INTENT_GENERAL)

    def test_greeting_with_product_terms_becomes_recommendation(self):
        self.assertEqual(detect_intent('Hi, I need a phone'), INTENT_RECOMMENDATION)


class SpecExtractionTest(TestCase):
    def test_ram_extraction(self):
        specs = _extract_all_specs('8GB RAM phone')
        self.assertEqual(specs.get('ram'), '8GB')

    def test_storage_extraction(self):
        specs = _extract_all_specs('256GB storage laptop')
        self.assertEqual(specs.get('storage'), '256GB')

    def test_battery_extraction(self):
        specs = _extract_all_specs('5000mAh battery phone')
        self.assertEqual(specs.get('battery'), '5000mAh')

    def test_camera_extraction(self):
        specs = _extract_all_specs('48MP camera')
        self.assertEqual(specs.get('camera'), '48MP')

    def test_rating_extraction(self):
        specs = _extract_all_specs('rating above 4.5')
        self.assertEqual(specs.get('rating'), 4.5)

    def test_full_spec_extraction(self):
        specs = _extract_all_specs('16GB RAM 512GB storage i7 laptop')
        self.assertEqual(specs.get('ram'), '16GB')
        self.assertEqual(specs.get('storage'), '512GB')
        self.assertIsNotNone(specs.get('processor'))


class FilterExtractionTest(TestCase):
    def test_extract_filters_basic(self):
        f = _extract_filters('Samsung phone under 25000')
        self.assertEqual(f.get('category'), 'Mobile')
        self.assertEqual(f.get('budget'), 25000)
        self.assertEqual(f.get('brand'), 'Samsung')

    def test_extract_filters_specs(self):
        f = _extract_filters('8GB RAM laptop')
        self.assertEqual(f.get('category'), 'Laptop')
        self.assertEqual(f.get('ram'), '8GB')


class TitleGenerationTest(TestCase):
    def test_title_with_brand_category(self):
        title = generate_title('Samsung phone under 30000')
        self.assertIn('Samsung', title)
        self.assertIn('Mobile', title)

    def test_title_with_category_only(self):
        title = generate_title('I need a laptop')
        self.assertIn('Laptop', title)

    def test_title_comparison(self):
        title = generate_title('Compare iPhone 15 and Galaxy S24')
        self.assertEqual(title, 'Product Comparison')

    def test_title_gaming(self):
        title = generate_title('Gaming laptop under 80000')
        self.assertIn('Gaming', title)

    def test_title_product_details(self):
        title = generate_title('Tell me about Galaxy S24')
        self.assertIn('Samsung', title)


class TfidfServiceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Product.objects.create(name='MacBook Pro', brand='Apple', category='Laptop', price=199000, ram='16GB', storage='512GB SSD', processor='M3 Pro', rating=4.8)
        Product.objects.create(name='Galaxy Book', brand='Samsung', category='Laptop', price=89990, ram='16GB', storage='512GB', processor='i7', rating=4.5)
        Product.objects.create(name='iPhone 15', brand='Apple', category='Mobile', price=79900, ram='8GB', storage='256GB', processor='A16', rating=4.6)

    def test_rank_by_similarity_returns_products(self):
        products = Product.objects.filter(category='Laptop')
        ranked = rank_by_similarity('MacBook', products)
        self.assertTrue(len(ranked) > 0)

    def test_find_similar_products(self):
        results = find_similar_products('Apple laptop', category='Laptop', max_results=3)
        self.assertTrue(len(results) > 0)


class EndToEndTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Product.objects.create(
            name='MacBook Air M3', brand='Apple', category='Laptop',
            price=114990, ram='8GB', storage='256GB SSD', processor='M3',
            battery='18 hours', display='13.6" Liquid Retina', rating=4.5
        )
        Product.objects.create(
            name='Galaxy S24', brand='Samsung', category='Mobile',
            price=79999, ram='8GB', storage='256GB', processor='Exynos 2400',
            battery='5000mAh', display='6.8" AMOLED', camera='50MP', rating=4.3
        )
        Product.objects.create(
            name='Galaxy A15', brand='Samsung', category='Mobile',
            price=15000, ram='6GB', storage='128GB', processor='Helio G99',
            battery='5000mAh', display='6.5" AMOLED', rating=4.0
        )

    def _post_message(self, message):
        return self.client.post(reverse('chatbot_view'), {
            'message': message,
            'session_id': '',
        })

    def test_greeting_does_not_return_products(self):
        response = self._post_message('Hi')
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('Hello', data['response'])
        self.assertNotIn('Galaxy', data['response'])

    def test_help_no_products(self):
        response = self._post_message('Help')
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('help', data['response'].lower())

    def test_samsung_phone_under_25000(self):
        response = self._post_message('Samsung phone under 25000')
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('Galaxy A15', data['response'])
        self.assertNotIn('Galaxy S24', data['response'])

    def test_comparison_response(self):
        response = self._post_message('Compare Galaxy S24 and Galaxy A15')
        data = response.json()
        self.assertTrue(data['success'])

    def test_product_details_response(self):
        response = self._post_message('Tell me about Galaxy S24')
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('Galaxy S24', data['response'])

    def test_search_analytics_logged(self):
        self._post_message('Samsung phone under 25000')
        self.assertTrue(SearchAnalytics.objects.exists())

    def test_messages_saved_to_session(self):
        self._post_message('Hello')
        self.assertEqual(ChatMessage.objects.count(), 2)

    def test_goodbye_response(self):
        response = self._post_message('Bye')
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('wonderful', data['response'].lower())

    def test_no_results_response(self):
        response = self._post_message('gaming laptop under 5000')
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('match', data['response'].lower())

    def test_greeting_with_product_terms_asks_budget(self):
        response = self._post_message('Hi, I need a phone')
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('budget', data['response'].lower())

    def test_category_isolation_mobile(self):
        response = self._post_message('mobile with 8GB RAM')
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('Galaxy', data['response'])
        self.assertNotIn('MacBook', data['response'])

    def test_response_contains_chips_and_follow_up(self):
        response = self._post_message('Samsung phone under 25000')
        data = response.json()
        self.assertIn('refinement-chips', data['response'])
        self.assertIn('match', data['response'].lower())


class MultiTurnConversationTest(TestCase):
    """Prove the backend multi-turn conversation system works end-to-end."""

    @classmethod
    def setUpTestData(cls):
        Product.objects.create(
            name='Galaxy S24', brand='Samsung', category='Mobile',
            price=79999, ram='8GB', storage='256GB', processor='Exynos 2400',
            battery='5000mAh', display='6.8" AMOLED', camera='50MP', rating=4.3
        )
        Product.objects.create(
            name='Galaxy A15', brand='Samsung', category='Mobile',
            price=15000, ram='6GB', storage='128GB', processor='Helio G99',
            battery='5000mAh', display='6.5" AMOLED', rating=4.0
        )
        Product.objects.create(
            name='iPhone 15', brand='Apple', category='Mobile',
            price=79900, ram='8GB', storage='256GB', processor='A16', rating=4.6
        )
        Product.objects.create(
            name='MacBook Air', brand='Apple', category='Laptop',
            price=114990, ram='8GB', storage='256GB', processor='M3', rating=4.5
        )

    def _post(self, message, session_id=''):
        if not session_id:
            resp = self.client.post(reverse('chatbot_new_chat'))
            session_id = resp.json()['session_id']
        response = self.client.post(reverse('chatbot_view'), {
            'message': message,
            'session_id': session_id,
        })
        data = response.json()
        return data, session_id

    # ===== Test 1: Multi-turn context persistence =====
    def test_multi_turn_accumulates_context_in_db(self):
        """Turn 1: category. Turn 2: budget. Turn 3: search uses both."""
        # Turn 1 — user says "phone"
        data1, sid = self._post('phone')
        self.assertTrue(data1['success'])
        session1 = ChatSession.objects.get(id=sid)
        ctx1 = session1.context
        self.assertEqual(ctx1.get('category'), 'Mobile',
                         msg="Turn 1: category=Mobile should be saved in DB context")
        self.assertIn('waiting_for', ctx1,
                      msg="Turn 1: bot should be waiting for budget")

        # Turn 2 — user says "20000"
        data2, _ = self._post('20000', sid)
        self.assertTrue(data2['success'])
        session2 = ChatSession.objects.get(id=sid)
        ctx2 = session2.context
        self.assertEqual(ctx2.get('category'), 'Mobile',
                         msg="Turn 2: category still Mobile in DB")
        self.assertEqual(ctx2.get('budget'), 20000,
                         msg="Turn 2: budget=20000 saved in DB")
        self.assertIn('has_shown_products', ctx2,
                      msg="Turn 2: products should have been shown")
        self.assertIn('refinement-chips', data2['response'],
                      msg="Turn 2: follow-up chips should be in response")

    # ===== Test 2: Refinement after products shown =====
    def test_refinement_cheaper_reduces_budget(self):
        """After products shown, 'cheaper' reduces budget by 30%."""
        data1, sid = self._post('Samsung phone under 30000')
        self.assertTrue(data1['success'])
        session1 = ChatSession.objects.get(id=sid)
        original_budget = session1.context.get('budget')

        data2, _ = self._post('cheaper', sid)
        self.assertTrue(data2['success'], msg="Refinement 'cheaper' should succeed")
        session2 = ChatSession.objects.get(id=sid)
        new_budget = session2.context.get('budget')
        self.assertIsNotNone(new_budget, msg="Budget should still exist after refinement")
        self.assertLess(new_budget, original_budget,
                        msg=f"Budget reduced from {original_budget} to {new_budget}")
        self.assertIn('refinement-chips', data2['response'],
                      msg="Response should contain follow-up chips after refinement")

    # ===== Test 3: Purpose chip filter applied =====
    def test_purpose_camera_adds_camera_filter(self):
        """After products shown, 'camera' chip sets purpose and camera filter."""
        data1, sid = self._post('phone under 50000')
        self.assertTrue(data1['success'])
        self.assertIn('refinement-chips', data1['response'],
                      msg="Purpose chips should be shown")

        data2, _ = self._post('camera', sid)
        self.assertTrue(data2['success'], msg="Camera chip should work")
        session2 = ChatSession.objects.get(id=sid)
        self.assertEqual(session2.context.get('purpose'), 'camera',
                         msg="Purpose=camera saved in DB")
        self.assertEqual(session2.context.get('camera'), '48MP',
                         msg="Camera chip should set 48MP filter in DB")

    # ===== Test 4: Session independence =====
    def test_sessions_have_independent_contexts(self):
        """Two sessions should have completely separate contexts."""
        data_a, sid_a = self._post('Apple phone')
        data_b, sid_b = self._post('Samsung laptop')
        self.assertNotEqual(sid_a, sid_b,
                            msg="New Chat should create different session IDs")

        session_a = ChatSession.objects.get(id=sid_a)
        session_b = ChatSession.objects.get(id=sid_b)
        self.assertEqual(session_a.context.get('brand'), 'Apple',
                         msg="Session A brand=Apple")
        self.assertEqual(session_b.context.get('brand'), 'Samsung',
                         msg="Session B brand=Samsung")
        self.assertEqual(session_a.context.get('category'), 'Mobile',
                         msg="Session A category=Mobile")
        self.assertEqual(session_b.context.get('category'), 'Laptop',
                         msg="Session B category=Laptop")

    # ===== Test 5: New Chat creates new session =====
    def test_new_chat_creates_new_session_object(self):
        """New Chat button must create a NEW ChatSession, not reuse old one."""
        resp1 = self.client.post(reverse('chatbot_new_chat'))
        sid1 = resp1.json()['session_id']
        resp2 = self.client.post(reverse('chatbot_new_chat'))
        sid2 = resp2.json()['session_id']
        self.assertNotEqual(sid1, sid2,
                            msg="Two New Chat calls must create different session IDs")
        self.assertEqual(ChatSession.objects.count(), 2,
                         msg="Exactly 2 ChatSession objects should exist")

    # ===== Test 6: Chat history loads correct session =====
    def test_chat_history_loads_correct_session(self):
        """get_session endpoint must return only that session's messages."""
        data1, sid = self._post('phone under 30000')
        self.assertTrue(data1['success'])
        msg_count_1 = ChatMessage.objects.filter(session_id=sid).count()

        # Send a second message to this session
        self._post('Samsung', sid)
        msg_count_2 = ChatMessage.objects.filter(session_id=sid).count()
        self.assertGreater(msg_count_2, msg_count_1,
                           msg="Second message should add to same session")

        # get_session should return ALL messages for this session
        resp = self.client.get(reverse('chatbot_get_session', args=[sid]))
        data = resp.json()
        self.assertEqual(data['id'], sid)
        self.assertEqual(len(data['messages']), msg_count_2,
                         msg="get_session returns exactly all messages in session")

        # A different session should return different messages
        data3, sid3 = self._post('laptop')
        resp3 = self.client.get(reverse('chatbot_get_session', args=[sid3]))
        data3 = resp3.json()
        self.assertNotEqual(len(data3['messages']), len(data['messages']),
                            msg="Different sessions have different message counts")

    # ===== Test 7: Greeting never searches =====
    def test_greeting_never_sets_context_or_searches(self):
        """Pure greeting should not set any search filters or show products."""
        data, sid = self._post('Hello')
        self.assertTrue(data['success'])
        session = ChatSession.objects.get(id=sid)
        self.assertNotIn('category', session.context,
                         msg="Greeting must not set category in context")
        self.assertNotIn('has_shown_products', session.context,
                         msg="Greeting must not set has_shown_products")
        self.assertNotIn('product-card', data['response'],
                         msg="Greeting must not contain product cards")
        self.assertIn('Hello', data['response'],
                      msg="Greeting should contain a hello message")

    # ===== Test 8: Greeting+product terms asks for more info =====
    def test_greeting_with_product_terms_asks_for_missing_fields(self):
        """"Hi, need a phone" should extract category and ask for budget."""
        data, sid = self._post('Hi, I need a phone')
        self.assertTrue(data['success'])
        session = ChatSession.objects.get(id=sid)
        self.assertEqual(session.context.get('category'), 'Mobile',
                         msg="Category extracted despite greeting prefix")
        self.assertIn('budget', data['response'].lower())

    # ===== Test 9: ask_assistant direct unit test =====
    def test_ask_assistant_returns_follow_up_chips(self):
        """Direct call to ask_assistant should return follow-up chips."""
        session = ChatSession.objects.create()
        resp_text, success = ask_assistant('Samsung phone under 20000', session=session)
        self.assertTrue(success)
        self.assertIn('refinement-chips', resp_text)
        self.assertIn('Samsung', resp_text)
        self.assertIn('Galaxy A15', resp_text)
        session.refresh_from_db()
        self.assertTrue(session.context.get('has_shown_products'))

    # ===== Test 10: _handle_refinement applied to context =====
    def test_handle_refinement_modifies_context(self):
        """Direct call to _handle_refinement should modify context in place."""
        session = ChatSession.objects.create()
        ctx = ConversationContext(session)
        ctx['category'] = 'Mobile'
        ctx['budget'] = 30000
        ctx['has_shown_products'] = True
        ctx.save()

        result = _handle_refinement('cheaper', ctx)
        self.assertTrue(result, msg="_handle_refinement('cheaper') should return True")
        self.assertLess(ctx.get('budget'), 30000,
                        msg="Budget should be less than 30000 after 'cheaper'")
        self.assertEqual(ctx.get('category'), 'Mobile',
                         msg="Category should remain unchanged")

        # Test 'only Samsung'
        ctx2 = ConversationContext(session)
        ctx2['category'] = 'Mobile'
        ctx2['budget'] = 50000
        ctx2['has_shown_products'] = True
        result2 = _handle_refinement('only Samsung', ctx2)
        self.assertTrue(result2, msg="'only Samsung' should be detected")
        self.assertEqual(ctx2.get('brand'), 'Samsung',
                         msg="Brand should be Samsung after 'only Samsung'")

        # Test 'more RAM'
        ctx3 = ConversationContext(session)
        ctx3['category'] = 'Mobile'
        ctx3['budget'] = 50000
        ctx3['has_shown_products'] = True
        result3 = _handle_refinement('more RAM', ctx3)
        self.assertTrue(result3, msg="'more RAM' should be detected")
        self.assertEqual(ctx3.get('ram'), '16GB',
                         msg="RAM should be 16GB after 'more RAM'")

        # Test 'AMOLED'
        ctx4 = ConversationContext(session)
        ctx4['category'] = 'Mobile'
        ctx4['has_shown_products'] = True
        result4 = _handle_refinement('AMOLED', ctx4)
        self.assertTrue(result4, msg="'AMOLED' should be detected")
        self.assertEqual(ctx4.get('display'), 'AMOLED',
                         msg="Display should be AMOLED")

        # Test non-refinement message
        ctx5 = ConversationContext(session)
        ctx5['category'] = 'Mobile'
        ctx5['has_shown_products'] = True
        result5 = _handle_refinement('what is the weather', ctx5)
        self.assertFalse(result5,
                         msg="Non-refinement should return False")

    # ===== Test 11: _generate_follow_up returns chips =====
    def test_generate_follow_up_returns_chips(self):
        """_generate_follow_up should always return refinement chips."""
        products = Product.objects.filter(category='Mobile')
        ctx = ConversationContext()
        ctx['category'] = 'Mobile'
        ctx['has_shown_products'] = True

        html = _generate_follow_up(products, ctx)
        self.assertIn('refinement-chips', html,
                      msg="Follow-up must contain refinement-chips")
        self.assertIn('match', html.lower(),
                      msg="Follow-up should mention finding a match")

    # ===== Test 12: Format with follow-up includes chips =====
    def test_format_with_follow_up_includes_chips(self):
        """_format_with_follow_up output must contain product cards AND chips."""
        products = Product.objects.filter(category='Mobile')
        applied = {'category': 'Mobile'}
        filters = {'category': 'Mobile'}
        ctx = ConversationContext()
        ctx['category'] = 'Mobile'

        resp_text, ok = _format_with_follow_up(products, applied, filters, ctx)
        self.assertTrue(ok)
        self.assertIn('product-card', resp_text,
                      msg="Response must contain product cards")
        self.assertIn('refinement-chips', resp_text,
                      msg="Response must contain refinement chips")

    # ===== Test 13: ConversationContext.save persists to DB =====
    def test_conversation_context_save_persists(self):
        """ConversationContext.save() must write to the database."""
        session = ChatSession.objects.create(context={})
        ctx = ConversationContext(session)
        ctx['category'] = 'Mobile'
        ctx['budget'] = 25000
        ctx['has_shown_products'] = True
        ctx.save()

        session.refresh_from_db()
        self.assertEqual(session.context.get('category'), 'Mobile')
        self.assertEqual(session.context.get('budget'), 25000)
        self.assertTrue(session.context.get('has_shown_products'))

    # ===== Test 14: ConversationContext.to_filters excludes internal keys =====
    def test_to_filters_excludes_internal_keys(self):
        """to_filters() must not include 'waiting_for', 'has_shown_products', 'purpose'."""
        ctx = ConversationContext()
        ctx['category'] = 'Mobile'
        ctx['budget'] = 30000
        ctx['has_shown_products'] = True
        ctx['waiting_for'] = 'budget'
        ctx['purpose'] = 'gaming'

        filters = ctx.to_filters()
        self.assertNotIn('has_shown_products', filters)
        self.assertNotIn('waiting_for', filters)
        self.assertNotIn('purpose', filters)
        self.assertEqual(filters.get('category'), 'Mobile')
        self.assertEqual(filters.get('budget'), 30000)

    # ===== Test 15: No results clears context =====
    def test_no_results_clears_context(self):
        """When no products match ANYWHERE, context should be cleared."""
        session = ChatSession.objects.create(context={'category': 'NonExistentCat', 'budget': 1})
        resp_text, success = ask_assistant('gizmo under 1 rupee', session=session)
        self.assertTrue(success)
        session.refresh_from_db()
        self.assertEqual(session.context, {},
                         msg="Context should be empty after no results anywhere")

    # ===== Test 16: Single product shows perfect match =====
    def test_single_product_shows_perfect_match(self):
        """When only 1 product matches, show 'Perfect Match' instead of chips."""
        Product.objects.create(
            name='Unique Phone', brand='OnePlus', category='Mobile',
            price=50000, ram='12GB', storage='256GB', processor='Snapdragon 8 Gen 3',
            rating=4.9, camera='50MP'
        )
        data, sid = self._post('OnePlus Unique Phone under 55000 with 12GB RAM')
        self.assertTrue(data['success'])
        self.assertIn('Perfect Match', data['response'],
                      msg="Single product match should show 'Perfect Match'")
        self.assertIn('refinement-chips', data['response'],
                      msg="Even perfect match should show refinement chips")
