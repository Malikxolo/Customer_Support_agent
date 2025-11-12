import os
import time
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Initialize DeepSeek client (uses OpenAI-compatible API)
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

def benchmark_reasoner_throughput(model="deepseek-reasoner", num_runs=5, show_thinking=False):
    """
    Benchmark DeepSeek Reasoner API throughput (includes reasoning/thinking tokens)
    
    Args:
        model: Model name ("deepseek-reasoner" for R1 with thinking)
        num_runs: Number of test runs to average
        show_thinking: Whether to print the reasoning process
    """
    
    # Test prompt that requires reasoning
    prompt = """Solve this problem step by step:
    A company has 3 factories. Factory A produces 100 units/day, Factory B produces 
    150 units/day, and Factory C produces 200 units/day. If Factory A operates 6 days/week, 
    Factory B operates 5 days/week, and Factory C operates 7 days/week, what is the 
    average daily production across all factories over a 4-week period?"""
    
    results = []
    
    print(f"🧠 Benchmarking DeepSeek Reasoner ({model})")
    print(f"Running {num_runs} tests...\n")
    
    for i in range(num_runs):
        try:
            start_time = time.time()
            
            # Make API call
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                stream=False
            )
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            # Extract token counts
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            
            # For reasoner models, extract reasoning tokens
            reasoning_content = ""
            answer_content = ""
            
            if hasattr(response.choices[0].message, 'reasoning_content'):
                reasoning_content = response.choices[0].message.reasoning_content or ""
            
            answer_content = response.choices[0].message.content or ""
            
            # Estimate reasoning tokens (rough approximation: ~4 chars per token)
            reasoning_tokens = len(reasoning_content) // 4 if reasoning_content else 0
            answer_tokens = completion_tokens - reasoning_tokens if reasoning_tokens else completion_tokens
            
            # Calculate throughput metrics
            reasoning_throughput = reasoning_tokens / elapsed_time if reasoning_tokens > 0 else 0
            answer_throughput = answer_tokens / elapsed_time if answer_tokens > 0 else 0
            total_output_throughput = completion_tokens / elapsed_time
            overall_throughput = total_tokens / elapsed_time
            
            results.append({
                'run': i + 1,
                'elapsed_time': elapsed_time,
                'prompt_tokens': prompt_tokens,
                'reasoning_tokens': reasoning_tokens,
                'answer_tokens': answer_tokens,
                'completion_tokens': completion_tokens,
                'total_tokens': total_tokens,
                'reasoning_throughput': reasoning_throughput,
                'answer_throughput': answer_throughput,
                'total_output_throughput': total_output_throughput,
                'overall_throughput': overall_throughput,
                'reasoning_content': reasoning_content,
                'answer_content': answer_content
            })
            
            print(f"Run {i+1}:")
            print(f"  ⏱️  Time: {elapsed_time:.2f}s")
            print(f"  📝 Prompt Tokens: {prompt_tokens}")
            print(f"  🧠 Reasoning Tokens: {reasoning_tokens}")
            print(f"  💬 Answer Tokens: {answer_tokens}")
            print(f"  📊 Total Completion: {completion_tokens}")
            print(f"  🔢 Total Tokens: {total_tokens}")
            print(f"  🚄 Reasoning Throughput: {reasoning_throughput:.2f} tokens/s")
            print(f"  🚄 Answer Throughput: {answer_throughput:.2f} tokens/s")
            print(f"  🚄 Total Output Throughput: {total_output_throughput:.2f} tokens/s")
            print(f"  🚄 Overall Throughput: {overall_throughput:.2f} tokens/s")
            
            if show_thinking and reasoning_content:
                print(f"\n  💭 Thinking Process:")
                print(f"  {reasoning_content[:300]}..." if len(reasoning_content) > 300 else f"  {reasoning_content}")
            
            print()
            
        except Exception as e:
            print(f"❌ Error in run {i+1}: {e}\n")
            continue
    
    # Calculate statistics
    if results:
        avg_reasoning_tokens = sum(r['reasoning_tokens'] for r in results) / len(results)
        avg_answer_tokens = sum(r['answer_tokens'] for r in results) / len(results)
        avg_completion_tokens = sum(r['completion_tokens'] for r in results) / len(results)
        avg_reasoning_throughput = sum(r['reasoning_throughput'] for r in results) / len(results)
        avg_answer_throughput = sum(r['answer_throughput'] for r in results) / len(results)
        avg_total_output_throughput = sum(r['total_output_throughput'] for r in results) / len(results)
        avg_overall_throughput = sum(r['overall_throughput'] for r in results) / len(results)
        avg_time = sum(r['elapsed_time'] for r in results) / len(results)
        
        print("=" * 60)
        print("📊 SUMMARY STATISTICS (WITH REASONING)")
        print("=" * 60)
        print(f"Average Reasoning Tokens: {avg_reasoning_tokens:.0f}")
        print(f"Average Answer Tokens: {avg_answer_tokens:.0f}")
        print(f"Average Total Completion Tokens: {avg_completion_tokens:.0f}")
        print(f"Average Reasoning Throughput: {avg_reasoning_throughput:.2f} tokens/s")
        print(f"Average Answer Throughput: {avg_answer_throughput:.2f} tokens/s")
        print(f"Average Total Output Throughput: {avg_total_output_throughput:.2f} tokens/s")
        print(f"Average Overall Throughput: {avg_overall_throughput:.2f} tokens/s")
        print(f"Average Response Time: {avg_time:.2f}s")
        print(f"Successful Runs: {len(results)}/{num_runs}")
        
    return results


def benchmark_streaming_with_thinking(model="deepseek-reasoner", num_runs=3):
    """
    Benchmark streaming throughput with reasoning tokens
    """
    
    prompt = """A train travels from City A to City B at 80 km/h and returns at 100 km/h. 
    If the total journey takes 9 hours, what is the distance between the two cities?"""
    
    results = []
    
    print(f"\n🌊 Benchmarking STREAMING with Reasoning")
    print(f"Running {num_runs} tests...\n")
    
    for i in range(num_runs):
        try:
            start_time = time.time()
            first_token_time = None
            reasoning_chunks = 0
            answer_chunks = 0
            in_reasoning = True
            
            # Make streaming API call
            stream = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                stream=True
            )
            
            for chunk in stream:
                current_time = time.time()
                
                # Track first token
                if first_token_time is None:
                    if (hasattr(chunk.choices[0].delta, 'reasoning_content') and 
                        chunk.choices[0].delta.reasoning_content) or \
                       (hasattr(chunk.choices[0].delta, 'content') and 
                        chunk.choices[0].delta.content):
                        first_token_time = current_time
                
                # Count reasoning vs answer chunks
                if hasattr(chunk.choices[0].delta, 'reasoning_content') and \
                   chunk.choices[0].delta.reasoning_content:
                    reasoning_chunks += 1
                elif hasattr(chunk.choices[0].delta, 'content') and \
                     chunk.choices[0].delta.content:
                    answer_chunks += 1
                    in_reasoning = False
            
            end_time = time.time()
            
            ttft = first_token_time - start_time if first_token_time else 0
            total_time = end_time - start_time
            streaming_time = end_time - first_token_time if first_token_time else total_time
            
            total_chunks = reasoning_chunks + answer_chunks
            streaming_throughput = total_chunks / streaming_time if streaming_time > 0 else 0
            
            results.append({
                'run': i + 1,
                'ttft': ttft,
                'total_time': total_time,
                'reasoning_chunks': reasoning_chunks,
                'answer_chunks': answer_chunks,
                'total_chunks': total_chunks,
                'streaming_throughput': streaming_throughput
            })
            
            print(f"Run {i+1}:")
            print(f"  ⚡ TTFT (Time to First Token): {ttft:.3f}s")
            print(f"  ⏱️  Total Time: {total_time:.2f}s")
            print(f"  🧠 Reasoning Chunks: {reasoning_chunks}")
            print(f"  💬 Answer Chunks: {answer_chunks}")
            print(f"  📝 Total Chunks: {total_chunks}")
            print(f"  🚄 Streaming Throughput: {streaming_throughput:.2f} chunks/s")
            print()
            
        except Exception as e:
            print(f"❌ Error in run {i+1}: {e}\n")
            continue
    
    # Calculate statistics
    if results:
        avg_ttft = sum(r['ttft'] for r in results) / len(results)
        avg_reasoning = sum(r['reasoning_chunks'] for r in results) / len(results)
        avg_answer = sum(r['answer_chunks'] for r in results) / len(results)
        avg_throughput = sum(r['streaming_throughput'] for r in results) / len(results)
        
        print("=" * 60)
        print("📊 STREAMING SUMMARY (WITH REASONING)")
        print("=" * 60)
        print(f"Average TTFT: {avg_ttft:.3f}s")
        print(f"Average Reasoning Chunks: {avg_reasoning:.0f}")
        print(f"Average Answer Chunks: {avg_answer:.0f}")
        print(f"Average Streaming Throughput: {avg_throughput:.2f} chunks/s")
        print(f"Successful Runs: {len(results)}/{num_runs}")
    
    return results


if __name__ == "__main__":
    # Test reasoner model (with thinking/reasoning)
    print("🧠 Testing DeepSeek Reasoner Model (with thinking)")
    print("=" * 60)
    
    reasoner_results = benchmark_reasoner_throughput(
        model="deepseek-reasoner",  # R1 model with reasoning
        num_runs=5,
        show_thinking=True  # Set to True to see thinking process
    )
    
    # Test streaming with reasoning
    streaming_results = benchmark_streaming_with_thinking(
        model="deepseek-reasoner",
        num_runs=3
    )
